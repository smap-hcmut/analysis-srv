"""DeduplicationService — custom MinHash dedup (no datasketch dependency).

Ported from core-analysis/src/smap/dedup/service.py with:
  - pydantic model_copy()  →  dataclasses.replace()
  - DedupClusterRecord / DedupAnalysisResult now dataclasses (see type.py)
"""

from __future__ import annotations

import dataclasses
import hashlib
from collections import defaultdict

from internal.normalization.type import MentionRecord
from ..type import DedupAnalysisResult, DedupClusterRecord

# When the total signature count is at or below this threshold, fall back to
# O(n²) brute-force comparison to catch near-duplicates that hash-banding
# misses in very small batches (empirically chosen; see core-analysis docs).
_BRUTE_FORCE_THRESHOLD = 64


class _UnionFind:
    def __init__(self, items: list[str]) -> None:
        self.parent: dict[str, str] = {item: item for item in items}

    def find(self, item: str) -> str:
        parent = self.parent.setdefault(item, item)
        if parent != item:
            self.parent[item] = self.find(parent)
        return self.parent[item]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


class DeduplicationService:
    def __init__(
        self,
        *,
        exact_enabled: bool = True,
        near_enabled: bool = True,
        min_text_length: int = 10,
        word_shingle_size: int = 3,
        char_shingle_size: int = 5,
        num_perm: int = 64,
        num_bands: int = 16,
        near_similarity_threshold: float = 0.82,
        max_bucket_size: int = 256,
    ) -> None:
        self.exact_enabled = exact_enabled
        self.near_enabled = near_enabled
        self.min_text_length = min_text_length
        self.word_shingle_size = word_shingle_size
        self.char_shingle_size = char_shingle_size
        self.num_perm = max(num_perm, 8)
        self.num_bands = max(1, min(num_bands, self.num_perm))
        self.rows_per_band = max(1, self.num_perm // self.num_bands)
        self.near_similarity_threshold = near_similarity_threshold
        self.max_bucket_size = max_bucket_size

    def annotate(
        self, mentions: list[MentionRecord]
    ) -> tuple[list[MentionRecord], DedupAnalysisResult]:
        if not mentions:
            return [], DedupAnalysisResult()
        exact_clusters = self._exact_clusters(mentions) if self.exact_enabled else []
        exact_members = {
            mid for cluster in exact_clusters for mid in cluster.mention_ids
        }
        near_clusters = (
            self._near_clusters(mentions, exact_members=exact_members)
            if self.near_enabled
            else []
        )
        annotations = self._annotation_map([*exact_clusters, *near_clusters])
        updated_mentions = [
            dataclasses.replace(mention, **annotations.get(mention.mention_id, {}))
            for mention in mentions
        ]
        return (
            updated_mentions,
            DedupAnalysisResult(
                mentions_updated=sum(1 for update in annotations.values() if update),
                exact_cluster_count=sum(
                    1 for c in exact_clusters if c.cluster_size > 1
                ),
                near_cluster_count=sum(1 for c in near_clusters if c.cluster_size > 1),
                clusters=[*exact_clusters, *near_clusters],
            ),
        )

    def _annotation_map(self, clusters: list[DedupClusterRecord]) -> dict[str, dict]:
        updates: dict[str, dict] = {}
        for cluster in clusters:
            weight = round(1.0 / max(cluster.cluster_size, 1), 6)
            for mention_id in cluster.mention_ids:
                updates[mention_id] = {
                    "dedup_cluster_id": cluster.dedup_cluster_id,
                    "dedup_kind": cluster.dedup_kind,
                    "dedup_representative_mention_id": cluster.representative_mention_id,
                    "dedup_cluster_size": cluster.cluster_size,
                    "dedup_similarity": cluster.similarity_proxy,
                    "dedup_weight": weight,
                }
        return updates

    def _exact_clusters(
        self, mentions: list[MentionRecord]
    ) -> list[DedupClusterRecord]:
        groups: dict[str, list[MentionRecord]] = defaultdict(list)
        for mention in mentions:
            fingerprint = self._fingerprint(mention.normalized_text_compact)
            if fingerprint is None:
                continue
            groups[fingerprint].append(mention)
        clusters: list[DedupClusterRecord] = []
        for fingerprint, members in sorted(groups.items()):
            if len(members) < 2:
                continue
            representative = self._representative(members)
            clusters.append(
                DedupClusterRecord(
                    dedup_cluster_id=f"exact:{fingerprint[:16]}",
                    dedup_kind="exact",
                    representative_mention_id=representative.mention_id,
                    representative_text=representative.raw_text,
                    mention_ids=[m.mention_id for m in members],
                    cluster_size=len(members),
                    similarity_proxy=1.0,
                    text_fingerprint=fingerprint,
                )
            )
        return clusters

    def _near_clusters(
        self,
        mentions: list[MentionRecord],
        *,
        exact_members: set[str],
    ) -> list[DedupClusterRecord]:
        candidates = [
            m
            for m in mentions
            if m.mention_id not in exact_members
            and len(m.normalized_text_compact) >= self.min_text_length
        ]
        if len(candidates) < 2:
            return []
        shingles = {
            m.mention_id: self._shingles(m.normalized_text_compact) for m in candidates
        }
        signatures = {
            mid: self._minhash_signature(items)
            for mid, items in shingles.items()
            if items
        }
        if len(signatures) < 2:
            return []
        buckets: dict[tuple[int, tuple[int, ...]], list[str]] = defaultdict(list)
        for mid, signature in signatures.items():
            for band_index in range(self.num_bands):
                start = band_index * self.rows_per_band
                end = start + self.rows_per_band
                band = signature[start:end]
                if not band:
                    continue
                buckets[(band_index, band)].append(mid)
        union_find = _UnionFind(list(signatures))
        for bucket in buckets.values():
            if len(bucket) < 2 or len(bucket) > self.max_bucket_size:
                continue
            for li in range(len(bucket)):
                for ri in range(li + 1, len(bucket)):
                    sim = self._jaccard(shingles[bucket[li]], shingles[bucket[ri]])
                    if sim >= self.near_similarity_threshold:
                        union_find.union(bucket[li], bucket[ri])
        if len(signatures) <= _BRUTE_FORCE_THRESHOLD:
            sig_ids = list(signatures)
            for li in range(len(sig_ids)):
                for ri in range(li + 1, len(sig_ids)):
                    sim = self._jaccard(shingles[sig_ids[li]], shingles[sig_ids[ri]])
                    if sim >= self.near_similarity_threshold:
                        union_find.union(sig_ids[li], sig_ids[ri])
        grouped: dict[str, list[MentionRecord]] = defaultdict(list)
        by_id = {m.mention_id: m for m in candidates}
        for mid in signatures:
            grouped[union_find.find(mid)].append(by_id[mid])
        clusters: list[DedupClusterRecord] = []
        for group_members in grouped.values():
            if len(group_members) < 2:
                continue
            representative = self._representative(group_members)
            similarity = self._cluster_similarity(group_members, shingles)
            cluster_hash = self._cluster_hash(group_members)
            clusters.append(
                DedupClusterRecord(
                    dedup_cluster_id=f"near:{cluster_hash[:16]}",
                    dedup_kind="near",
                    representative_mention_id=representative.mention_id,
                    representative_text=representative.raw_text,
                    mention_ids=sorted(m.mention_id for m in group_members),
                    cluster_size=len(group_members),
                    similarity_proxy=similarity,
                    text_fingerprint=cluster_hash,
                )
            )
        return sorted(clusters, key=lambda c: (-c.cluster_size, c.dedup_cluster_id))

    def _fingerprint(self, text: str) -> str | None:
        compact = " ".join(text.split())
        if len(compact) < self.min_text_length:
            return None
        return hashlib.blake2b(compact.encode("utf-8"), digest_size=20).hexdigest()

    def _shingles(self, text: str) -> set[str]:
        tokens = [t for t in text.split() if t]
        if len(tokens) >= self.word_shingle_size:
            return {
                " ".join(tokens[i : i + self.word_shingle_size])
                for i in range(len(tokens) - self.word_shingle_size + 1)
            }
        compact = text.replace(" ", "")
        if len(compact) >= self.char_shingle_size:
            return {
                compact[i : i + self.char_shingle_size]
                for i in range(len(compact) - self.char_shingle_size + 1)
            }
        return {text} if text else set()

    def _minhash_signature(self, shingles: set[str]) -> tuple[int, ...]:
        hashed = [
            int(hashlib.blake2b(s.encode("utf-8"), digest_size=8).hexdigest(), 16)
            for s in shingles
        ]
        if not hashed:
            return ()
        signature: list[int] = []
        for seed in range(self.num_perm):
            signature.append(
                min(
                    (v ^ ((seed + 1) * 0x9E3779B97F4A7C15)) & 0xFFFFFFFFFFFFFFFF
                    for v in hashed
                )
            )
        return tuple(signature)

    def _jaccard(self, left: set[str], right: set[str]) -> float:
        if not left and not right:
            return 1.0
        union = left | right
        if not union:
            return 0.0
        return round(len(left & right) / len(union), 4)

    def _representative(self, mentions: list[MentionRecord]) -> MentionRecord:
        return sorted(
            mentions,
            key=lambda m: (-len(m.normalized_text_compact), m.depth, m.mention_id),
        )[0]

    def _cluster_similarity(
        self, mentions: list[MentionRecord], shingles: dict[str, set[str]]
    ) -> float:
        if len(mentions) < 2:
            return 1.0
        total = 0.0
        pair_count = 0
        for li in range(len(mentions)):
            for ri in range(li + 1, len(mentions)):
                total += self._jaccard(
                    shingles[mentions[li].mention_id],
                    shingles[mentions[ri].mention_id],
                )
                pair_count += 1
        return round(total / pair_count, 4) if pair_count > 0 else 1.0

    def _cluster_hash(self, mentions: list[MentionRecord]) -> str:
        payload = "|".join(sorted(m.normalized_text_compact for m in mentions))
        return hashlib.blake2b(payload.encode("utf-8"), digest_size=20).hexdigest()


__all__ = ["DeduplicationService"]
