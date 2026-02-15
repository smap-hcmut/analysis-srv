"""Analyzed Post Domain - CRUD operations for analyzed posts."""

from .interface import IAnalyzedPostUseCase
from .type import CreateAnalyzedPostInput, UpdateAnalyzedPostInput
from .usecase.new import New as NewAnalyzedPostUseCase

__all__ = [
    "IAnalyzedPostUseCase",
    "CreateAnalyzedPostInput",
    "UpdateAnalyzedPostInput",
    "NewAnalyzedPostUseCase",
]
