from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from .constant import *


@dataclass
class SpacyYakeConfig:
    """SpaCy-YAKE extractor configuration.

    Attributes:
        spacy_model: SpaCy model name (e.g., 'en_core_web_sm', 'vi_core_news_lg')
        yake_language: Language code for YAKE (e.g., 'en', 'vi')
        yake_n: Max n-gram size for YAKE
        yake_dedup_lim: Deduplication threshold for YAKE
        yake_max_keywords: Max keywords to extract with YAKE
        max_keywords: Max keywords to return in final result
        entity_weight: Score weight for named entities
        chunk_weight: Score weight for noun chunks
    """

    spacy_model: str = DEFAULT_SPACY_MODEL
    yake_language: str = DEFAULT_YAKE_LANGUAGE
    yake_n: int = DEFAULT_YAKE_N
    yake_dedup_lim: float = DEFAULT_YAKE_DEDUP_LIM
    yake_max_keywords: int = DEFAULT_YAKE_MAX_KEYWORDS
    max_keywords: int = DEFAULT_MAX_KEYWORDS
    entity_weight: float = DEFAULT_ENTITY_WEIGHT
    chunk_weight: float = DEFAULT_CHUNK_WEIGHT

    def __post_init__(self):
        """Validate configuration."""
        if self.yake_n <= 0:
            raise ValueError(f"yake_n must be positive, got {self.yake_n}")

        if self.max_keywords <= 0:
            raise ValueError(f"max_keywords must be positive, got {self.max_keywords}")

        if not 0.0 <= self.entity_weight <= 1.0:
            raise ValueError(
                f"entity_weight must be in [0, 1], got {self.entity_weight}"
            )

        if not 0.0 <= self.chunk_weight <= 1.0:
            raise ValueError(f"chunk_weight must be in [0, 1], got {self.chunk_weight}")


@dataclass
class SpacyYakeItem:
    """Single keyword extraction result."""

    keyword: str
    score: float
    rank: int
    type: str  # Can be from KeywordType enum or entity_{label}
    relevance: float


@dataclass
class SpacyYakeOutput:
    """Result of SpaCy-YAKE keyword extraction."""

    keywords: List[SpacyYakeItem] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    method_name: str = "spacy_yake"
    confidence_score: float = 0.0
    success: bool = True
    error_message: Optional[str] = None
