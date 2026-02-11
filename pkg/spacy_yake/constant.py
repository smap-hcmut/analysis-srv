from enum import Enum

# Default Configuration
DEFAULT_SPACY_MODEL = "vi_core_news_sm"
DEFAULT_YAKE_LANGUAGE = "vi"
DEFAULT_YAKE_N = 3
DEFAULT_YAKE_DEDUP_LIM = 0.9
DEFAULT_YAKE_MAX_KEYWORDS = 10
DEFAULT_MAX_KEYWORDS = 10
DEFAULT_ENTITY_WEIGHT = 1.5
DEFAULT_CHUNK_WEIGHT = 1.0

# Validation Constants
MAX_TEXT_LENGTH_WARNING = 10000
MIN_TEXT_LENGTH = 1

# Extraction Constants
ENTITY_MAX_WORDS = 3
ENTITY_MIN_LENGTH = 1
MAX_ENTITIES_RETURN = 15
MAX_NOUN_CHUNKS_RETURN = 20
MIN_NOUN_CHUNK_LENGTH = 1
MIN_NOUN_PHRASE_LENGTH = 3
MIN_TOKEN_LENGTH_BLANK = 2

# Scoring Constants
KEYWORD_COUNT_DIVISOR = 30.0
SCORE_MAX_LIMIT = 1.0
DIVERSITY_DIVISOR = 4.0
DIVERSITY_BONUS_MAX = 0.2
ENTITY_TYPES_DIVISOR = 5.0
ENTITY_BONUS_MAX = 0.15
VARIANCE_BONUS_MAX = 0.15

# Error Messages
ERROR_MODEL_NOT_INITIALIZED = "SpaCy model or YAKE extractor not initialized."
ERROR_INVALID_INPUT = "Input text is invalid or empty."


class SpacyModel(str, Enum):
    VI_CORE_NEWS_SM = "vi_core_news_sm"
    VI_CORE_NEWS_LG = "vi_core_news_lg"
    XX_ENT_WIKI_SM = "xx_ent_wiki_sm"
    EN_CORE_WEB_SM = "en_core_web_sm"
    BLANK_VI = "vi"


class POSTag(str, Enum):
    NOUN = "NOUN"
    PROPN = "PROPN"
    ADJ = "ADJ"


class KeywordType(str, Enum):
    STATISTICAL = "statistical"
    SYNTACTIC = "syntactic"
    ENTITY = "entity"
