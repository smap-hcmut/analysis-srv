"""Domain repository errors for analyzed_post."""


class RepositoryError(Exception):
    """Base exception for repository operations."""
    pass


class ErrFailedToCreate(RepositoryError):
    """Raised when insert operation fails."""
    pass


class ErrFailedToGet(RepositoryError):
    """Raised when select operation fails."""
    pass


class ErrFailedToUpdate(RepositoryError):
    """Raised when update operation fails."""
    pass


class ErrFailedToDelete(RepositoryError):
    """Raised when delete operation fails."""
    pass


class ErrFailedToUpsert(RepositoryError):
    """Raised when upsert operation fails."""
    pass


class ErrInvalidData(RepositoryError):
    """Raised when input data is invalid."""
    pass


__all__ = [
    "RepositoryError",
    "ErrFailedToCreate",
    "ErrFailedToGet",
    "ErrFailedToUpdate",
    "ErrFailedToDelete",
    "ErrFailedToUpsert",
    "ErrInvalidData",
]
