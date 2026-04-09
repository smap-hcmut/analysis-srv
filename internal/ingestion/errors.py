"""Ingestion module errors."""


class IngestionError(Exception):
    """Base error for ingestion failures."""


class InvalidRecordError(IngestionError):
    """Raised when a UAPRecord fails validation."""

    def __init__(self, record_id: str, reason: str) -> None:
        self.record_id = record_id
        self.reason = reason
        super().__init__(f"invalid record '{record_id}': {reason}")


__all__ = ["IngestionError", "InvalidRecordError"]
