"""Analyzed Post Domain — CRUD operations for analyzed posts."""

from .interface import IAnalyzedPostUseCase
from .type import CreateAnalyzedPostInput, UpdateAnalyzedPostInput
from .errors import ErrPostNotFound, ErrInvalidInput, ErrDuplicatePost
from .usecase.new import New as NewAnalyzedPostUseCase

__all__ = [
    # Interface
    "IAnalyzedPostUseCase",
    # Types
    "CreateAnalyzedPostInput",
    "UpdateAnalyzedPostInput",
    # Errors
    "ErrPostNotFound",
    "ErrInvalidInput",
    "ErrDuplicatePost",
    # Factory
    "NewAnalyzedPostUseCase",
]
