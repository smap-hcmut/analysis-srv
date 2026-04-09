"""Normalization errors."""


class NormalizationError(Exception):
    """Base error for normalization failures."""


class TextNormalizationError(NormalizationError):
    """Raised when a single record cannot be normalized."""

    def __init__(self, mention_id: str, reason: str) -> None:
        self.mention_id = mention_id
        self.reason = reason
        super().__init__(f"normalization failed for '{mention_id}': {reason}")


__all__ = ["NormalizationError", "TextNormalizationError"]
