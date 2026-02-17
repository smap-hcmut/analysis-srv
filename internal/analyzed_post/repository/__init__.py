"""Analyzed Post Repository.

Exports:
- IAnalyzedPostRepository: Repository interface
- Options: All option structs
- Errors: Domain repository errors
- New: Factory function
"""

from .interface import IAnalyzedPostRepository
from .new import New
from .option import (
    CreateOptions,
    UpsertOptions,
    GetOneOptions,
    ListOptions,
    UpdateStatusOptions,
    DeleteOptions,
)
from .errors import (
    RepositoryError,
    ErrFailedToCreate,
    ErrFailedToGet,
    ErrFailedToUpdate,
    ErrFailedToDelete,
    ErrFailedToUpsert,
    ErrInvalidData,
)

__all__ = [
    "IAnalyzedPostRepository",
    "New",
    "CreateOptions",
    "UpsertOptions",
    "GetOneOptions",
    "ListOptions",
    "UpdateStatusOptions",
    "DeleteOptions",
    "RepositoryError",
    "ErrFailedToCreate",
    "ErrFailedToGet",
    "ErrFailedToUpdate",
    "ErrFailedToDelete",
    "ErrFailedToUpsert",
    "ErrInvalidData",
]
