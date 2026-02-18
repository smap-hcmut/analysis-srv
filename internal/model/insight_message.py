"""Insight message format for Kafka output.

This module defines the message structure published to Kafka topic
'smap.analytics.output' for Knowledge Service and downstream consumers.

Message format: JSON array of InsightMessage objects (batch).
"""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Project:
    project_id: str = ""
    entity_type: str = ""
    entity_name: str = ""
    brand: str = ""
    campaign_id: Optional[str] = None


@dataclass
class Author:
    author_id: Optional[str] = None
    display_name: Optional[str] = None
    author_type: str = "user"


@dataclass
class Identity:
    source_type: str = ""
    source_id: str = ""
    doc_id: str = ""
    doc_type: str = "post"
    url: Optional[str] = None
    language: Optional[str] = None
    published_at: Optional[str] = None
    ingested_at: Optional[str] = None
    author: Author = field(default_factory=Author)


@dataclass
class Content:
    text: str = ""
    clean_text: str = ""
    summary: str = ""


@dataclass
class NLPSentiment:
    label: str = "NEUTRAL"
    score: float = 0.0
    confidence: str = "LOW"
    explanation: str = ""


@dataclass
class NLPAspect:
    aspect: str = ""
    polarity: str = "NEUTRAL"
    confidence: float = 0.0
    evidence: str = ""


@dataclass
class NLPEntity:
    type: str = ""
    value: str = ""
    confidence: float = 0.0


@dataclass
class NLP:
    sentiment: NLPSentiment = field(default_factory=NLPSentiment)
    aspects: list[NLPAspect] = field(default_factory=list)
    entities: list[NLPEntity] = field(default_factory=list)


@dataclass
class BusinessEngagement:
    like_count: int = 0
    comment_count: int = 0
    share_count: int = 0
    view_count: int = 0


@dataclass
class BusinessImpact:
    engagement: BusinessEngagement = field(default_factory=BusinessEngagement)
    impact_score: float = 0.0
    priority: str = "LOW"


@dataclass
class BusinessAlert:
    alert_type: str = ""
    severity: str = "LOW"
    reason: str = ""
    suggested_action: str = ""


@dataclass
class Business:
    impact: BusinessImpact = field(default_factory=BusinessImpact)
    alerts: list[BusinessAlert] = field(default_factory=list)


@dataclass
class RAGQualityGate:
    min_length_ok: bool = False
    has_aspect: bool = False
    not_spam: bool = True


@dataclass
class RAGIndex:
    should_index: bool = False
    quality_gate: RAGQualityGate = field(default_factory=RAGQualityGate)


@dataclass
class RAGCitation:
    source: str = ""
    title: str = ""
    snippet: str = ""
    url: str = ""
    published_at: str = ""


@dataclass
class RAGVectorRef:
    provider: str = "qdrant"
    collection: str = ""
    point_id: str = ""


@dataclass
class RAG:
    index: RAGIndex = field(default_factory=RAGIndex)
    citation: RAGCitation = field(default_factory=RAGCitation)
    vector_ref: RAGVectorRef = field(default_factory=RAGVectorRef)


@dataclass
class ProvenanceStep:
    step: str = ""
    model: str = ""
    at: str = ""


@dataclass
class Provenance:
    raw_ref: str = ""
    pipeline: list[ProvenanceStep] = field(default_factory=list)


@dataclass
class InsightMessage:
    message_version: str = "1.0"
    event_id: str = ""
    project: Project = field(default_factory=Project)
    identity: Identity = field(default_factory=Identity)
    content: Content = field(default_factory=Content)
    nlp: NLP = field(default_factory=NLP)
    business: Business = field(default_factory=Business)
    rag: RAG = field(default_factory=RAG)
    provenance: Provenance = field(default_factory=Provenance)

    def to_dict(self) -> dict[str, Any]:
        return _to_dict_recursive(self)


def _to_dict_recursive(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _to_dict_recursive(v) for k, v in obj.__dict__.items()}
    if isinstance(obj, list):
        return [_to_dict_recursive(item) for item in obj]
    return obj
