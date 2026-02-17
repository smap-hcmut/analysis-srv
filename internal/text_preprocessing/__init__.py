"""Text preprocessing domain."""

from .interface import ITextProcessing
from .type import Config, Output
from .errors import ErrInvalidInput, ErrPreprocessingFailed
from .usecase import TextProcessing, New

__all__ = [
    "ITextProcessing",
    "Config",
    "Output",
    "ErrInvalidInput",
    "ErrPreprocessingFailed",
    "TextProcessing",
    "New",
]
