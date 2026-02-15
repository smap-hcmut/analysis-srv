# Field names
FIELD_CONTENT = "content"
FIELD_TEXT = "text"
FIELD_TRANSCRIPTION = "transcription"
FIELD_COMMENTS = "comments"
FIELD_LIKES = "likes"

# Output field names
FIELD_CLEAN_TEXT = "clean_text"
FIELD_STATS = "stats"
FIELD_SOURCE_BREAKDOWN = "source_breakdown"

# Stats field names
STAT_TOTAL_LENGTH = "total_length"
STAT_IS_TOO_SHORT = "is_too_short"
STAT_HASHTAG_RATIO = "hashtag_ratio"
STAT_REDUCTION_RATIO = "reduction_ratio"
STAT_HAS_TRANSCRIPTION = "has_transcription"
STAT_HAS_PHONE = "has_phone"
STAT_HAS_SPAM_KEYWORD = "has_spam_keyword"

# Source breakdown field names
SOURCE_CAPTION_LEN = "caption_len"
SOURCE_TRANSCRIPT_LEN = "transcript_len"
SOURCE_COMMENTS_LEN = "comments_len"

# Regex patterns
PATTERN_URL = r"(?:http[s]?://|www\.)(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
PATTERN_EMOJI = (
    "["
    "\U0001f600-\U0001f64f"  # emoticons
    "\U0001f300-\U0001f5ff"  # symbols & pictographs
    "\U0001f680-\U0001f6ff"  # transport & map symbols
    "\U0001f1e0-\U0001f1ff"  # flags (iOS)
    "\U00002702-\U000027b0"
    "\U000024c2-\U0001f251"
    "]+"
)
PATTERN_HASHTAG = r"#(\w+)"
PATTERN_WHITESPACE = r"\s+"
PATTERN_PHONE_VN = r"(03|05|07|08|09|01[2689])\d{8}"
PATTERN_DUPLICATE_PERIODS = r"\.{2,}"

# Spam keywords
SPAM_KEYWORDS = [
    "vay vốn",
    "lãi suất",
    "giải ngân",
    "bán sim",
    "tuyển dụng",
]

# Teencode dictionary
TEENCODE_DICT = {
    "ko": "không",
    "k": "không",
    "khg": "không",
    "hk": "không",
    "vkl": "rất",
    "vcl": "rất",
    "ae": "anh em",
    "tml": "thì",
    "thì ml": "thì",
    "dc": "được",
    "đc": "được",
    "vs": "với",
    "mik": "mình",
    "mk": "mình",
    "e": "em",
    "a": "anh",
    "c": "chị",
    "m": "mày",
    "t": "tao",
    "nc": "nói chuyện",
    "nch": "nói chuyện",
    "oke": "ok",
    "okie": "ok",
    "uk": "ừ",
    "uhm": "ừ",
    "uh": "ừ",
    "ny": "người yêu",
    "cx": "cũng",
    "cg": "cũng",
    "j": "gì",
    "gi": "gì",
}

# Punctuation to strip
TRAILING_PUNCTUATION = ".!?;:,"

# Unicode normalization form
UNICODE_NORMALIZATION_FORM = "NFKC"

# Default configuration values
DEFAULT_MIN_TEXT_LENGTH = 10
DEFAULT_MAX_COMMENTS = 5

__all__ = [
    "FIELD_CONTENT",
    "FIELD_TEXT",
    "FIELD_TRANSCRIPTION",
    "FIELD_COMMENTS",
    "FIELD_LIKES",
    "FIELD_CLEAN_TEXT",
    "FIELD_STATS",
    "FIELD_SOURCE_BREAKDOWN",
    "STAT_TOTAL_LENGTH",
    "STAT_IS_TOO_SHORT",
    "STAT_HASHTAG_RATIO",
    "STAT_REDUCTION_RATIO",
    "STAT_HAS_TRANSCRIPTION",
    "STAT_HAS_PHONE",
    "STAT_HAS_SPAM_KEYWORD",
    "SOURCE_CAPTION_LEN",
    "SOURCE_TRANSCRIPT_LEN",
    "SOURCE_COMMENTS_LEN",
    "PATTERN_URL",
    "PATTERN_EMOJI",
    "PATTERN_HASHTAG",
    "PATTERN_WHITESPACE",
    "PATTERN_PHONE_VN",
    "PATTERN_DUPLICATE_PERIODS",
    "SPAM_KEYWORDS",
    "TEENCODE_DICT",
    "TRAILING_PUNCTUATION",
    "UNICODE_NORMALIZATION_FORM",
    "DEFAULT_MIN_TEXT_LENGTH",
    "DEFAULT_MAX_COMMENTS",
]
