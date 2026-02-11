from enum import Enum

DEFAULT_MODEL_PATH = "models/phobert"
DEFAULT_MAX_LENGTH = 256
MAX_SEQUENCE_LENGTH_LIMIT = 512
MODEL_FILE_NAME = "phobert.onnx"

DEFAULT_NEUTRAL_RESPONSE = "I don't know the sentiment of your comment."
DEFAULT_PROBABILITIES = [0.0, 0.0, 1.0]

# Tensor Constants
TENSOR_TYPE_PT = "pt"
PADDING_STRATEGY = "max_length"

# Keys
KEY_INPUT_IDS = "input_ids"
KEY_ATTENTION_MASK = "attention_mask"
KEY_NEGATIVE = "NEGATIVE"
KEY_POSITIVE = "POSITIVE"
KEY_NEUTRAL = "NEUTRAL"


class Sentiment(int, Enum):
    NEGATIVE = 0
    POSITIVE = 1
    NEUTRAL = 2


class SentimentLabel(str, Enum):
    POSITIVE = "Tích cực"
    NEGATIVE = "Tiêu cực"
    NEUTRAL = "Trung tính"


# Map model output index to Sentiment Enum
SENTIMENT_INDEX_MAP = {
    0: Sentiment.NEGATIVE,
    1: Sentiment.POSITIVE,
    2: Sentiment.NEUTRAL,
}

SENTIMENT_LABELS = {
    Sentiment.POSITIVE: SentimentLabel.POSITIVE.value,
    Sentiment.NEGATIVE: SentimentLabel.NEGATIVE.value,
    Sentiment.NEUTRAL: SentimentLabel.NEUTRAL.value,
}

ERROR_MODEL_DIR_NOT_FOUND = "Model directory not found at: {path}"
ERROR_MODEL_FILE_NOT_FOUND = "Model file not found at: {path}"
ERROR_MODEL_LOAD_FAILED = "Failed to load model: {error}"
