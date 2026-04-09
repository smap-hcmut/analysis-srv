"""Ingestion constants — doc_type → depth mapping."""

# UAPRecord content.doc_type → pipeline depth
DOC_TYPE_DEPTH: dict[str, int] = {
    "post": 0,
    "video": 0,
    "news": 0,
    "feedback": 0,
    "comment": 1,
    "reply": 2,
}

# doc_type values considered root-level (depth == 0)
ROOT_DOC_TYPES: frozenset[str] = frozenset({"post", "video", "news", "feedback"})

__all__ = ["DOC_TYPE_DEPTH", "ROOT_DOC_TYPES"]
