"""Constants for AI infrastructure (PhoBERT and SpaCy-YAKE)."""

import os
from pathlib import Path

# ============================================================================
# PhoBERT Configuration
# ============================================================================

# Model Configuration (loaded from environment or defaults)
DEFAULT_MODEL_PATH = os.getenv("PHOBERT_MODEL_PATH", "infrastructure/phobert/models")
DEFAULT_MAX_LENGTH = int(os.getenv("PHOBERT_MAX_LENGTH", "128"))
MODEL_FILE_NAME = os.getenv("PHOBERT_MODEL_FILE", "model_quantized.onnx")

# Required Model Files
REQUIRED_MODEL_FILES = [
    "model_quantized.onnx",
    "config.json",
    "vocab.txt",
    "special_tokens_map.json",
    "tokenizer_config.json",
]

# Sentiment Mapping: model output index -> rating (1-5 stars)
# Updated for 3-class sentiment model based on wonrax/phobert-base-vietnamese-sentiment
# Model mapping: 0=NEG, 1=POS, 2=NEU (from config.json id2label)
# Maps 3 classes to 5-star rating scale for backward compatibility, using
# more "extreme" endpoints so that NEG and POS are clearly separated.
SENTIMENT_MAP = {
    0: 1,  # NEG (index 0) -> 1 star (Very Negative)
    1: 5,  # POS (index 1) -> 5 stars (Very Positive)
    2: 3,  # NEU (index 2) -> 3 stars (Neutral)
}

# Sentiment Labels
SENTIMENT_LABELS = {
    1: "VERY_NEGATIVE",
    2: "NEGATIVE",
    3: "NEUTRAL",
    4: "POSITIVE",
    5: "VERY_POSITIVE",
}

# Default Neutral Response (for empty/invalid input)
DEFAULT_NEUTRAL_RESPONSE = {
    "rating": 3,
    "sentiment": "NEUTRAL",
    "label": "NEUTRAL",  # Alias for backward compatibility
    "confidence": 0.0,
}

# Default Probability Distribution (uniform) for 3-class model
DEFAULT_PROBABILITIES = {
    "NEGATIVE": 0.333,
    "NEUTRAL": 0.334,
    "POSITIVE": 0.333,
}

# Error Messages
ERROR_MODEL_DIR_NOT_FOUND = (
    "Model directory not found: {path}\nRun 'make download-phobert' to download the model."
)
ERROR_MODEL_FILE_NOT_FOUND = (
    "Model file not found: {path}\nRun 'make download-phobert' to download the model."
)
ERROR_MODEL_LOAD_FAILED = "Failed to load PhoBERT model: {error}"

# ============================================================================
# SpaCy-YAKE Configuration
# ============================================================================

# SpaCy Model Configuration
# Use multilingual model (xx_ent_wiki_sm) as default for compatibility
# Vietnamese models (vi_core_news_*) are community-built and may not work with spaCy 3.8.11
# The code will automatically fallback to blank("vi") if no model is available
DEFAULT_SPACY_MODEL = os.getenv("SPACY_MODEL", "xx_ent_wiki_sm")

# YAKE Configuration
DEFAULT_YAKE_LANGUAGE = os.getenv("YAKE_LANGUAGE", "vi")
DEFAULT_YAKE_N = int(os.getenv("YAKE_N", "2"))
DEFAULT_YAKE_DEDUP_LIM = float(os.getenv("YAKE_DEDUP_LIM", "0.8"))
DEFAULT_YAKE_MAX_KEYWORDS = int(os.getenv("YAKE_MAX_KEYWORDS", "30"))

# Extraction Configuration
DEFAULT_MAX_KEYWORDS = int(os.getenv("MAX_KEYWORDS", "30"))
DEFAULT_ENTITY_WEIGHT = float(os.getenv("ENTITY_WEIGHT", "0.7"))
DEFAULT_CHUNK_WEIGHT = float(os.getenv("CHUNK_WEIGHT", "0.5"))

# Aspect Mapping Configuration
DEFAULT_ASPECT_DICTIONARY_PATH = os.getenv("ASPECT_DICTIONARY_PATH", "config/aspects.yaml")
DEFAULT_UNKNOWN_ASPECT_LABEL = os.getenv("UNKNOWN_ASPECT_LABEL", "UNKNOWN")
ENABLE_ASPECT_MAPPING = os.getenv("ENABLE_ASPECT_MAPPING", "false").lower() == "true"

# Error Messages
ERROR_MODEL_NOT_INITIALIZED = "SpaCy or YAKE models not initialized"
ERROR_INVALID_INPUT = "Invalid input text"
ERROR_ASPECT_DICTIONARY_NOT_FOUND = "Aspect dictionary file not found: {path}"

# ============================================================================
# Sentiment Analysis Configuration (ABSA)
# ============================================================================

# Context Windowing
# Tighter default window keeps sentiment focused around each keyword and reduces
# "sentiment bleeding" between clauses. Can be overridden via CONTEXT_WINDOW_SIZE.
DEFAULT_CONTEXT_WINDOW_SIZE = int(os.getenv("CONTEXT_WINDOW_SIZE", "30"))

# Sentiment Thresholds (for 3-class mapping)
THRESHOLD_POSITIVE = float(os.getenv("THRESHOLD_POSITIVE", "0.25"))
THRESHOLD_NEGATIVE = float(os.getenv("THRESHOLD_NEGATIVE", "-0.25"))

# Score Mapping (5-class rating to numeric score)
SCORE_MAP = {
    1: -1.0,  # VERY_NEGATIVE
    2: -0.5,  # NEGATIVE
    3: 0.0,  # NEUTRAL
    4: 0.5,  # POSITIVE
    5: 1.0,  # VERY_POSITIVE
}

# 3-Class Sentiment Labels (for ABSA)
ABSA_LABELS = {
    "POSITIVE": "POSITIVE",
    "NEGATIVE": "NEGATIVE",
    "NEUTRAL": "NEUTRAL",
}
