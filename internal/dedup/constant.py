"""Dedup constants."""

# Minimum text length for a mention to be considered for near-dedup
MIN_TEXT_LENGTH_DEFAULT: int = 10

# Default MinHash parameters
NUM_PERM_DEFAULT: int = 64
NUM_BANDS_DEFAULT: int = 16
NEAR_SIMILARITY_THRESHOLD_DEFAULT: float = 0.82

__all__ = [
    "MIN_TEXT_LENGTH_DEFAULT",
    "NUM_PERM_DEFAULT",
    "NUM_BANDS_DEFAULT",
    "NEAR_SIMILARITY_THRESHOLD_DEFAULT",
]
