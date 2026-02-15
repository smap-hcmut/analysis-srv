"""Text preprocessing domain."""

from .interface import ITextProcessing
from .type import Config, Output
from .usecase import TextProcessing, New

__all__ = [
    "ITextProcessing",
    "Config",
    "Output",
    "TextProcessing",
    "New",
]
