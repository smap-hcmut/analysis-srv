"""Topic enricher — ontology-guided + TF-IDF fallback.

Ported from core-analysis smap/enrichers/topic.py:
- When ontology_registry is provided: first matches mentions against
  ontology TopicDefinition.seed_phrases for known topics, producing
  high-confidence topic facts.
- Falls back to FallbackTopicProvider (TF-IDF union-find clustering)
  for mentions that don't match any ontology topic.

Self-contained: no external smap.* imports.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from internal.enrichment.type import (
    FactProvenance,
    TopicArtifactFact,
    TopicFact,
)

if TYPE_CHECKING:
    from internal.ontology.usecase.file_registry import FileOntologyRegistry

# ---------------------------------------------------------------------------
# Stopwords for TF-IDF
# ---------------------------------------------------------------------------

_STOPWORDS = frozenset(
    {
        # Vietnamese
        "và",
        "là",
        "của",
        "cho",
        "với",
        "trong",
        "trên",
        "dưới",
        "nếu",
        "khi",
        "vì",
        "bởi",
        "mà",
        "thì",
        "đã",
        "đang",
        "sẽ",
        "có",
        "không",
        "này",
        "đó",
        "các",
        "một",
        "những",
        "được",
        "bị",
        "tôi",
        "anh",
        "chị",
        "em",
        "ông",
        "bà",
        "mình",
        "họ",
        "nó",
        "người",
        "mấy",
        "bác",
        "hơn",
        "rất",
        "quá",
        "lắm",
        # English
        "the",
        "and",
        "with",
        "that",
        "this",
        "for",
        "not",
        "are",
        "was",
        "but",
        "have",
        "from",
        "has",
        "its",
        "url",
        "http",
        "https",
    }
)

_MIN_TOKEN_LEN = 3
_CLUSTER_THRESHOLD = 2  # min shared top-tokens to be in same cluster
_TOP_N_TOKENS = 8  # top tokens per document for clustering


# ---------------------------------------------------------------------------
# Internal data structures
# ---------------------------------------------------------------------------


@dataclass
class _DocumentRecord:
    document_id: str
    mention_id: str
    source_uap_id: str
    text: str
    top_tokens: list[str] = field(default_factory=list)


@dataclass
class TopicAssignment:
    document_id: str
    topic_key: str
    topic_label: str
    confidence: float


@dataclass
class TopicArtifact:
    topic_key: str
    topic_label: str
    top_terms: list[str]
    topic_size: int
    representative_document_ids: list[str]


@dataclass
class TopicDiscovery:
    assignments: list[TopicAssignment]
    artifacts: list[TopicArtifact]


# ---------------------------------------------------------------------------
# FallbackTopicProvider
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase tokens, filtering stopwords."""
    tokens = re.findall(r"[\w\u00c0-\u024f\u1e00-\u1eff]+", text.lower())
    return [
        token
        for token in tokens
        if len(token) >= _MIN_TOKEN_LEN and token not in _STOPWORDS
    ]


def _top_tokens(text: str, n: int = _TOP_N_TOKENS) -> list[str]:
    """Return top-n most frequent non-stopword tokens from text."""
    counts = Counter(_tokenize(text))
    return [token for token, _ in counts.most_common(n)]


def _topic_key_for_terms(terms: list[str]) -> str:
    """Stable topic key derived from sorted top terms."""
    canonical = "_".join(sorted(terms[:3]))
    digest = hashlib.md5(canonical.encode("utf-8"), usedforsecurity=False).hexdigest()[
        :8
    ]
    return f"topic-{digest}"


def _topic_label_for_terms(terms: list[str]) -> str:
    """Human-readable label from top terms."""
    return " / ".join(terms[:3]) if terms else "misc"


class FallbackTopicProvider:
    """TF-IDF-based topic provider using token overlap clustering.

    Algorithm:
    1. Extract top-N tokens per document.
    2. Cluster documents that share >= CLUSTER_THRESHOLD tokens.
    3. Each cluster → one topic. Singletons → own unique topic.
    """

    version = "fallback-tfidf-v1"

    def discover(
        self,
        documents: list[_DocumentRecord],
    ) -> TopicDiscovery:
        if not documents:
            return TopicDiscovery(assignments=[], artifacts=[])

        # Step 1: compute top tokens per doc
        for doc in documents:
            doc.top_tokens = _top_tokens(doc.text)

        # Step 2: union-find clustering by token overlap
        parent: dict[int, int] = {i: i for i in range(len(documents))}

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x: int, y: int) -> None:
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py

        for i in range(len(documents)):
            tokens_i = set(documents[i].top_tokens)
            for j in range(i + 1, len(documents)):
                tokens_j = set(documents[j].top_tokens)
                shared = tokens_i & tokens_j
                if len(shared) >= _CLUSTER_THRESHOLD:
                    union(i, j)

        # Step 3: group by root
        clusters: dict[int, list[int]] = defaultdict(list)
        for i in range(len(documents)):
            clusters[find(i)].append(i)

        assignments: list[TopicAssignment] = []
        artifacts: list[TopicArtifact] = []

        for root, members in clusters.items():
            # Aggregate top terms across cluster
            all_tokens: list[str] = []
            for idx in members:
                all_tokens.extend(documents[idx].top_tokens)
            term_counts = Counter(all_tokens)
            top_terms = [token for token, _ in term_counts.most_common(6)]
            if not top_terms:
                top_terms = ["misc"]

            topic_key = _topic_key_for_terms(top_terms)
            topic_label = _topic_label_for_terms(top_terms)
            rep_ids = [documents[idx].document_id for idx in members[:5]]
            cluster_size = len(members)

            confidence = min(0.35 + cluster_size * 0.05, 0.85)

            artifacts.append(
                TopicArtifact(
                    topic_key=topic_key,
                    topic_label=topic_label,
                    top_terms=top_terms,
                    topic_size=cluster_size,
                    representative_document_ids=rep_ids,
                )
            )
            for idx in members:
                assignments.append(
                    TopicAssignment(
                        document_id=documents[idx].document_id,
                        topic_key=topic_key,
                        topic_label=topic_label,
                        confidence=round(confidence, 3),
                    )
                )

        return TopicDiscovery(assignments=assignments, artifacts=artifacts)


# ---------------------------------------------------------------------------
# SimplifiedTopicCandidateEnricher
# ---------------------------------------------------------------------------

PROVIDER_VERSION = "topic-simplified-v1"


class SimplifiedTopicCandidateEnricher:
    """Topic enricher with ontology-guided matching + TF-IDF fallback.

    When ontology_registry is provided, first matches mentions against
    ontology TopicDefinition.seed_phrases for known topics, then falls
    back to TF-IDF clustering for unmatched mentions.

    Matches the interface expected by EnricherService.enrich_mentions():
      prepare(mentions, contexts, *, entity_facts, aspect_facts, issue_facts)
      enrich(mention, context) -> list[TopicFact]
      artifacts() -> list[TopicArtifactFact]
    """

    provider_version = PROVIDER_VERSION
    name = "topic"

    def __init__(
        self,
        topic_provider: FallbackTopicProvider | None = None,
        ontology_registry: "FileOntologyRegistry | None" = None,
    ) -> None:
        self._provider = topic_provider or FallbackTopicProvider()
        self._topic_facts_by_mention: dict[str, list[TopicFact]] = defaultdict(list)
        self._topic_artifacts: list[TopicArtifactFact] = []
        self._ontology_registry = ontology_registry
        self._topic_seeds: dict[str, list[str]] = {}
        if ontology_registry is not None:
            self._topic_seeds = ontology_registry.topic_seed_phrases()

    def prepare(
        self,
        mentions: list[Any],  # list[MentionRecord]
        contexts: list[Any],  # list[MentionContext]
        *,
        entity_facts: list[Any] | None = None,
        aspect_facts: list[Any] | None = None,
        issue_facts: list[Any] | None = None,
    ) -> None:
        """Build topic assignments for all mentions.

        When ontology topic seeds are available, first match mentions against
        known topic seed_phrases. Remaining mentions go through TF-IDF clustering.
        """
        del contexts, entity_facts, aspect_facts, issue_facts

        self._topic_facts_by_mention = defaultdict(list)
        self._topic_artifacts = []

        if not mentions:
            return

        # Step 1: Ontology-guided topic matching
        unmatched_mentions: list[Any] = []
        ontology_topic_counts: dict[str, int] = defaultdict(int)

        if self._topic_seeds:
            for mention in mentions:
                text_lower = mention.raw_text.lower()
                matched = False
                for topic_key, seed_phrases in self._topic_seeds.items():
                    for phrase in seed_phrases:
                        if phrase.lower() in text_lower:
                            # Get topic label from ontology
                            topic_label = topic_key
                            if self._ontology_registry:
                                for t in self._ontology_registry.topics:
                                    if t.topic_key == topic_key:
                                        topic_label = t.label
                                        break

                            self._topic_facts_by_mention[mention.mention_id].append(
                                TopicFact(
                                    mention_id=mention.mention_id,
                                    source_uap_id=mention.source_uap_id,
                                    topic_key=topic_key,
                                    topic_label=topic_label,
                                    reporting_status="reportable",
                                    confidence=0.75,
                                    segment_id=None,
                                    provenance=FactProvenance(
                                        source_uap_id=mention.source_uap_id,
                                        mention_id=mention.mention_id,
                                        provider_version=self.provider_version,
                                        rule_version="topic-ontology-seed-v1",
                                        evidence_text=phrase,
                                    ),
                                )
                            )
                            ontology_topic_counts[topic_key] += 1
                            matched = True
                            break  # one topic match per seed set is enough
                    if matched:
                        break
                if not matched:
                    unmatched_mentions.append(mention)
        else:
            unmatched_mentions = list(mentions)

        # Build artifacts for ontology-matched topics
        for topic_key, count in ontology_topic_counts.items():
            topic_label = topic_key
            if self._ontology_registry:
                for t in self._ontology_registry.topics:
                    if t.topic_key == topic_key:
                        topic_label = t.label
                        break
            seed_phrases = self._topic_seeds.get(topic_key, [])
            self._topic_artifacts.append(
                TopicArtifactFact(
                    topic_key=topic_key,
                    topic_label=topic_label,
                    topic_size=count,
                    top_terms=seed_phrases[:6],
                    representative_document_ids=[],
                    artifact_version=self.provider_version,
                    provider_name="ontology-seed",
                    reporting_status="reportable",
                    provenance=FactProvenance(
                        source_uap_id="batch",
                        mention_id="ontology",
                        provider_version=self.provider_version,
                        rule_version="topic-ontology-seed-v1",
                        evidence_text=topic_label,
                    ),
                )
            )

        # Step 2: TF-IDF fallback for unmatched mentions
        if not unmatched_mentions:
            return

        # Build document records
        documents: list[_DocumentRecord] = []
        for mention in unmatched_mentions:
            doc = _DocumentRecord(
                document_id=f"{mention.mention_id}:whole",
                mention_id=mention.mention_id,
                source_uap_id=mention.source_uap_id,
                text=mention.raw_text,
            )
            documents.append(doc)

        discovery = self._provider.discover(documents)

        # Index assignments by mention_id
        doc_to_mention: dict[str, tuple[str, str]] = {
            doc.document_id: (doc.mention_id, doc.source_uap_id) for doc in documents
        }

        for assignment in discovery.assignments:
            mention_id, source_uap_id = doc_to_mention[assignment.document_id]
            self._topic_facts_by_mention[mention_id].append(
                TopicFact(
                    mention_id=mention_id,
                    source_uap_id=source_uap_id,
                    topic_key=assignment.topic_key,
                    topic_label=assignment.topic_label,
                    reporting_status="reportable",
                    confidence=assignment.confidence,
                    segment_id=None,
                    provenance=FactProvenance(
                        source_uap_id=source_uap_id,
                        mention_id=mention_id,
                        provider_version=self.provider_version,
                        rule_version="topic-tfidf-v1",
                        evidence_text=assignment.topic_label,
                    ),
                )
            )

        for artifact in discovery.artifacts:
            self._topic_artifacts.append(
                TopicArtifactFact(
                    topic_key=artifact.topic_key,
                    topic_label=artifact.topic_label,
                    topic_size=artifact.topic_size,
                    top_terms=artifact.top_terms,
                    representative_document_ids=artifact.representative_document_ids,
                    artifact_version=self.provider_version,
                    provider_name="fallback-tfidf",
                    reporting_status="reportable",
                    provenance=FactProvenance(
                        source_uap_id="batch",
                        mention_id=artifact.representative_document_ids[0].split(":")[0]
                        if artifact.representative_document_ids
                        else "unknown",
                        provider_version=self.provider_version,
                        rule_version="topic-tfidf-v1",
                        evidence_text=artifact.topic_label,
                    ),
                )
            )

    def enrich(
        self,
        mention: Any,  # MentionRecord
        context: Any,  # MentionContext | None
    ) -> list[TopicFact]:
        """Return TopicFacts for this mention (populated during prepare())."""
        return list(self._topic_facts_by_mention.get(mention.mention_id, []))

    def artifacts(self) -> list[TopicArtifactFact]:
        """Return TopicArtifactFacts built during prepare()."""
        return list(self._topic_artifacts)
