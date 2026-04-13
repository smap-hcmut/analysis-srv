# Phase 3 — Ingestion, Normalization, Dedup, Spam, Threads

> **Depends on:** Phase 2 (pipeline orchestrator)
> **Source:** `core-analysis/src/smap/ingestion/`, `normalization/`, `dedup/`, `quality/`, `threads/`
> **New deps:** `datasketch` (MinHash), `fasttext` (lang detect), `polars`

## Mục tiêu

Port các processing stages từ core-analysis để nâng chất lượng dữ liệu trước khi enrichment.
Kết quả: silver-layer facts (`MentionRecord`, dedup clusters, thread bundles) chuẩn cho Phase 4.

## Folder structure

```
internal/ingestion/
├── interface.py, type.py, constant.py, errors.py
└── usecase/
    ├── new.py, usecase.py
    ├── ingest_batch.py       # validate + convert IngestedBatchBundle
    ├── kafka_adapter.py      # KafkaToIngestedBatchAdapter
    └── helpers.py

internal/normalization/
├── interface.py, type.py, constant.py, errors.py
└── usecase/
    ├── new.py, usecase.py
    ├── normalize_mentions.py   # text clean + lang detect → MentionRecord[]
    └── helpers.py              # fastText loader, text_normalize()

internal/dedup/
├── interface.py, type.py, constant.py, errors.py
└── usecase/
    ├── new.py, usecase.py
    ├── annotate_dedup.py       # exact hash + MinHash LSH
    └── helpers.py

internal/spam/
├── interface.py, type.py, constant.py, errors.py
└── usecase/
    ├── new.py, usecase.py
    ├── score_authors.py        # author inorganic scoring, burst detection
    └── helpers.py

internal/threads/
├── interface.py, type.py, constant.py, errors.py
└── usecase/
    ├── new.py, usecase.py
    ├── build_threads.py        # reconstruct ThreadBundle từ parent_id/root_id
    └── helpers.py
```

## `ingestion/` — `KafkaToIngestedBatchAdapter`

```python
# internal/ingestion/usecase/kafka_adapter.py

def adapt_kafka_records(
    records: list[UAPRecord],  # từ Kafka consumer hiện tại
    project_id: str,
    campaign_id: str,
) -> IngestedBatchBundle:
    """
    Convert UAPRecord[] (Kafka format) → IngestedBatchBundle (core-analysis format).
    Đây là điểm giao duy nhất giữa old Kafka consumer và new pipeline.
    """
    posts, comments, replies = [], [], []
    for rec in records:
        depth = getattr(rec.hierarchy, "depth", 0) if hasattr(rec, "hierarchy") else 0
        if depth == 0:
            posts.append(_uap_to_post_record(rec, project_id, campaign_id))
        elif depth == 1:
            comments.append(_uap_to_comment_record(rec, project_id, campaign_id))
        else:
            replies.append(_uap_to_reply_record(rec, project_id, campaign_id))

    return IngestedBatchBundle(
        project_id=project_id,
        campaign_id=campaign_id,
        posts=posts,
        comments=comments,
        replies=replies,
    )
```

Key mapping (`UAPRecord` → `PostRecord`/`CommentRecord`/`ReplyRecord`):

| UAPRecord field | Core field | Notes |
|---|---|---|
| `ingest.source.source_id` | `identity.uap_id` | primary key |
| `ingest.source.source_type` | `identity.platform` | lowercase |
| `content.doc_type` | `identity.uap_type` | `"post"/"comment"/"reply"` |
| `content.media_type` | `identity.uap_media_type` | giải quyết gap uap_media_type Phase 1 |
| `content.text` | `content.text` | |
| `content.published_at` | `temporal.posted_at` | |
| `signals.engagement.*` | `engagement.*` | |
| `hierarchy.parent_id` | `hierarchy.parent_id` | |
| `hierarchy.root_id` | `hierarchy.root_id` | |
| `author.*` | `author.*` | |

## `normalization/` — `normalize_mentions()`

```python
# internal/normalization/usecase/normalize_mentions.py
# Port từ core-analysis/src/smap/normalization/

import fasttext

_lang_model = None  # lazy-load

def normalize_mentions(
    batch: IngestedBatchBundle,
    lang_model_path: str,
) -> list[MentionRecord]:
    """
    Mỗi post/comment/reply → 1 MentionRecord với:
    - mention_id (UUID stable)
    - clean_text (bỏ hashtag, emoji, normalize whitespace)
    - language (fastText detect)
    - depth, root_id, parent_id
    - dedup_weight = 1.0 (default, sẽ điều chỉnh trong dedup stage)
    """
    model = _get_lang_model(lang_model_path)
    mentions = []
    for record in _iter_all(batch):
        clean = _clean_text(record.content.text)
        lang = _detect_language(model, clean)
        mentions.append(MentionRecord(
            mention_id=_stable_uuid(record.identity.uap_id),
            source_uap_id=record.identity.uap_id,
            author_id=record.author.id,
            platform=record.identity.platform,
            depth=record.hierarchy.depth,
            root_id=record.hierarchy.root_id,
            parent_id=record.hierarchy.parent_id,
            posted_at=record.temporal.posted_at,
            clean_text=clean,
            language=lang,
            dedup_weight=1.0,
            quality_weight=1.0,
        ))
    return mentions

def _clean_text(text: str) -> str:
    """Remove hashtags, emojis, normalize whitespace."""
    import re
    text = re.sub(r"#\S+", "", text)             # hashtags
    text = re.sub(r"[^\w\s\u00C0-\u024F\u1E00-\u1EFF.,!?]", " ", text)  # emojis/special
    return re.sub(r"\s+", " ", text).strip()
```

## `dedup/` — MinHash LSH

```python
# internal/dedup/usecase/annotate_dedup.py
# Port từ core-analysis/src/smap/dedup/
# Requires: pip install datasketch

from datasketch import MinHash, MinHashLSH

EXACT_HASH_THRESHOLD = 1.0
NEAR_DEDUP_THRESHOLD = 0.85   # Jaccard similarity
NUM_PERM = 128

def annotate_dedup(mentions: list[MentionRecord]) -> list[DedupAnnotation]:
    """
    Returns dedup annotations: (mention_id, dedup_kind, cluster_id, dedup_weight)
    - EXACT: identical clean_text
    - NEAR: Jaccard >= 0.85
    - UNIQUE: no match
    """
    # Phase 1: exact hash
    seen_hashes = {}
    annotations = {}
    for m in mentions:
        h = _text_hash(m.clean_text)
        if h in seen_hashes:
            annotations[m.mention_id] = DedupAnnotation(
                mention_id=m.mention_id,
                dedup_kind="exact",
                cluster_id=seen_hashes[h],
                dedup_weight=0.0,
            )
        else:
            seen_hashes[h] = m.mention_id
            annotations[m.mention_id] = DedupAnnotation(
                mention_id=m.mention_id,
                dedup_kind="unique",
                cluster_id=m.mention_id,
                dedup_weight=1.0,
            )

    # Phase 2: MinHash LSH cho near-dedup (chỉ với UNIQUE từ phase 1)
    lsh = MinHashLSH(threshold=NEAR_DEDUP_THRESHOLD, num_perm=NUM_PERM)
    minhashes = {}
    for m in mentions:
        if annotations[m.mention_id].dedup_kind != "unique":
            continue
        mh = MinHash(num_perm=NUM_PERM)
        for word in m.clean_text.lower().split():
            mh.update(word.encode("utf8"))
        minhashes[m.mention_id] = mh
        lsh.insert(m.mention_id, mh)

    for mid, mh in minhashes.items():
        neighbors = lsh.query(mh)
        neighbors = [n for n in neighbors if n != mid]
        if neighbors:
            rep = min(neighbors)  # canonical = lexicographically smallest
            annotations[mid] = DedupAnnotation(
                mention_id=mid,
                dedup_kind="near",
                cluster_id=rep,
                dedup_weight=0.3,  # partial weight cho near-dup
            )

    return list(annotations.values())
```

## `spam/` — Author inorganic scoring

```python
# internal/spam/usecase/score_authors.py
# Port từ core-analysis/src/smap/quality/

def score_authors(mentions: list[MentionRecord]) -> list[AuthorQualityRecord]:
    """
    Tính inorganic score cho mỗi author dựa trên:
    1. Burstiness: nhiều posts trong khoảng thời gian ngắn
    2. Repetition: nhiều posts với near-identical content (overlap với dedup)
    3. Low-engagement pattern: nhiều posts không có engagement
    """
    from collections import defaultdict
    author_mentions: dict[str, list] = defaultdict(list)
    for m in mentions:
        author_mentions[m.author_id].append(m)

    results = []
    for author_id, author_posts in author_mentions.items():
        burst_score = _compute_burstiness(author_posts)
        inorganic_score = min(burst_score, 1.0)
        results.append(AuthorQualityRecord(
            author_id=author_id,
            mention_count=len(author_posts),
            author_suspicious=(inorganic_score > 0.7),
            author_inorganic_score=inorganic_score,
            burstiness_score=burst_score,
        ))
    return results
```

## `threads/` — Thread builder

```python
# internal/threads/usecase/build_threads.py
# Port từ core-analysis/src/smap/threads/

def build_threads(mentions: list[MentionRecord]) -> ThreadBundle:
    """
    Reconstruct thread hierarchy từ parent_id/root_id.
    Output: ThreadBundle với:
    - thread_summaries: list[ThreadSummary] (1 per root post)
    - thread_edges: list[ThreadEdge] (parent → child relationships)
    """
    from collections import defaultdict

    # Group by root_id
    roots: dict[str, list] = defaultdict(list)
    for m in mentions:
        roots[m.root_id or m.mention_id].append(m)

    summaries = []
    edges = []
    for root_id, thread_mentions in roots.items():
        comments = [m for m in thread_mentions if m.depth == 1]
        replies  = [m for m in thread_mentions if m.depth >= 2]
        max_depth = max((m.depth for m in thread_mentions), default=0)
        summaries.append(ThreadSummary(
            root_id=root_id,
            total_mentions=len(thread_mentions),
            comment_count=len(comments),
            reply_count=len(replies),
            max_depth_observed=max_depth,
            top_comment_ids=[m.mention_id for m in sorted(comments, key=lambda x: x.posted_at)[:5]],
        ))
        for m in thread_mentions:
            if m.parent_id and m.parent_id != m.mention_id:
                edges.append(ThreadEdge(parent_id=m.parent_id, child_id=m.mention_id, depth=m.depth))

    return ThreadBundle(summaries=summaries, edges=edges)
```

## Libraries cần thêm vào `pyproject.toml`

```toml
dependencies = [
    # ... existing ...
    "datasketch>=1.6",       # MinHash LSH
    "fasttext-wheel>=0.9",   # language detection (pre-built wheel)
    "polars>=0.20",          # data processing
]
```

## Gate Phase 3

- [ ] `KafkaToIngestedBatchAdapter` pass với 100 sample UAP records (no parse error)
- [ ] `normalize_mentions()` detect Vietnamese >= 90% accuracy trên sample facial-cleanser
- [ ] `annotate_dedup()` exact dedup rate trên golden dataset trong expected range
- [ ] `build_threads()` reconstruct đúng thread hierarchy (verify bằng known dataset)
