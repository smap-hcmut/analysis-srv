# Sentiment labels (3-class ABSA format)
LABEL_POSITIVE = "POSITIVE"
LABEL_NEGATIVE = "NEGATIVE"
LABEL_NEUTRAL = "NEUTRAL"

# Score mapping from 5-star rating to sentiment score (-1.0 to 1.0)
SCORE_RATING_1 = -1.0  # Very negative
SCORE_RATING_2 = -0.5  # Negative
SCORE_RATING_3 = 0.0   # Neutral
SCORE_RATING_4 = 0.5   # Positive
SCORE_RATING_5 = 1.0   # Very positive

# Thresholds for sentiment classification
DEFAULT_THRESHOLD_POSITIVE = 0.25
DEFAULT_THRESHOLD_NEGATIVE = -0.25

# Context window configuration
DEFAULT_CONTEXT_WINDOW_SIZE = 100  # characters

# Delimiters for context windowing
DELIMITERS = [".", ",", ";", "!", "?", "nhưng", "tuy nhiên", "mặc dù", "bù lại"]

# Whitespace characters
WHITESPACE_CHARS = " \t\n"

# Punctuation to strip
STRIP_PUNCTUATION = " \n\t.,;!?"

# Default rating (neutral)
DEFAULT_RATING = 3

# Metadata keys
METADATA_LABEL = "label"
METADATA_SCORE = "score"
METADATA_RATING = "rating"
METADATA_CONFIDENCE = "confidence"
METADATA_PROBABILITIES = "probabilities"
METADATA_MENTIONS = "mentions"
METADATA_KEYWORDS = "keywords"
METADATA_ERROR = "error"

# Keyword fields
KEYWORD_FIELD_KEYWORD = "keyword"
KEYWORD_FIELD_ASPECT = "aspect"
KEYWORD_FIELD_POSITION = "position"
KEYWORD_FIELD_SCORE = "score"
KEYWORD_FIELD_SOURCE = "source"

# Default aspect
DEFAULT_ASPECT = "GENERAL"

# Output keys
OUTPUT_OVERALL = "overall"
OUTPUT_ASPECTS = "aspects"

__all__ = [
    "LABEL_POSITIVE",
    "LABEL_NEGATIVE",
    "LABEL_NEUTRAL",
    "SCORE_RATING_1",
    "SCORE_RATING_2",
    "SCORE_RATING_3",
    "SCORE_RATING_4",
    "SCORE_RATING_5",
    "DEFAULT_THRESHOLD_POSITIVE",
    "DEFAULT_THRESHOLD_NEGATIVE",
    "DEFAULT_CONTEXT_WINDOW_SIZE",
    "DELIMITERS",
    "WHITESPACE_CHARS",
    "STRIP_PUNCTUATION",
    "DEFAULT_RATING",
    "METADATA_LABEL",
    "METADATA_SCORE",
    "METADATA_RATING",
    "METADATA_CONFIDENCE",
    "METADATA_PROBABILITIES",
    "METADATA_MENTIONS",
    "METADATA_KEYWORDS",
    "METADATA_ERROR",
    "KEYWORD_FIELD_KEYWORD",
    "KEYWORD_FIELD_ASPECT",
    "KEYWORD_FIELD_POSITION",
    "KEYWORD_FIELD_SCORE",
    "KEYWORD_FIELD_SOURCE",
    "DEFAULT_ASPECT",
    "OUTPUT_OVERALL",
    "OUTPUT_ASPECTS",
]
