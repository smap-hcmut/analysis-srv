"""storage/usecase/new.py — factory for StorageRepository."""

from __future__ import annotations

from internal.storage.usecase.usecase import StorageRepository


def new_storage_repository() -> StorageRepository:
    """Return the default filesystem-backed StorageRepository."""
    return StorageRepository()


__all__ = ["new_storage_repository"]
