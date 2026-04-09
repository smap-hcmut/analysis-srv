"""crisis/usecase/new.py — factory for CrisisUseCase."""

from internal.crisis.usecase.usecase import CrisisUseCase


def new_crisis_usecase() -> CrisisUseCase:
    """Instantiate CrisisUseCase (no external deps)."""
    return CrisisUseCase()


__all__ = ["new_crisis_usecase"]
