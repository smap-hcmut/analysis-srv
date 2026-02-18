class RepositoryError(Exception):
    pass


class ErrFailedToCreate(RepositoryError):
    pass


class ErrFailedToGet(RepositoryError):
    pass


class ErrFailedToUpdate(RepositoryError):
    pass


class ErrFailedToDelete(RepositoryError):
    pass


class ErrFailedToUpsert(RepositoryError):
    pass


class ErrInvalidData(RepositoryError):
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
