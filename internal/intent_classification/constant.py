# Intent categories
INTENT_CRISIS = "CRISIS"
INTENT_SEEDING = "SEEDING"
INTENT_SPAM = "SPAM"
INTENT_COMPLAINT = "COMPLAINT"
INTENT_LEAD = "LEAD"
INTENT_SUPPORT = "SUPPORT"
INTENT_DISCUSSION = "DISCUSSION"

# Intent priorities (for conflict resolution)
PRIORITY_CRISIS = 10
PRIORITY_SEEDING = 9
PRIORITY_SPAM = 9  # Same as SEEDING
PRIORITY_COMPLAINT = 7
PRIORITY_LEAD = 5
PRIORITY_SUPPORT = 4
PRIORITY_DISCUSSION = 1

# Confidence calculation
CONFIDENCE_BASE = 0.5
CONFIDENCE_INCREMENT = 0.1
CONFIDENCE_MAX = 1.0

# Default configuration values
DEFAULT_CONFIDENCE_THRESHOLD = 0.5
DEFAULT_PATTERNS_PATH = None

# Default patterns for each intent
DEFAULT_CRISIS_PATTERNS = [
    r"tẩy\s*chay",
    r"lừa\s*đảo",
    r"lừa.*đảo",
    r"scam",
    r"phốt",
    r"bóc\s*phốt",
    r"bóc.*phốt",
    r"lừa\s*gạt",
    r"gian\s*lận",
    r"cảnh\s*báo",
]

DEFAULT_SEEDING_PATTERNS = [
    r"\b0\d{9,10}\b",  # Vietnamese phone numbers
    r"zalo.*\d{9,10}",
    r"inbox.*giá",
    r"inbox.*mua",
    r"liên\s*hệ.*mua",
    r"liên\s*hệ.*\d{9}",
    r"inbox.*shop",
    r"chat.*shop",
]

DEFAULT_SPAM_PATTERNS = [
    r"vay\s*tiền",
    r"vay\s*vốn",
    r"bán\s*sim",
    r"lãi\s*suất",
    r"giải\s*ngân",
    r"tuyển\s*dụng",
    r"cần\s*gấp",
    r"thu\s*nhập",
]

DEFAULT_COMPLAINT_PATTERNS = [
    r"lỗi.*(không|chưa).*sửa",
    r"lỗi.*chưa.*khắc\s*phục",
    r"thất\s*vọng",
    r"tệ\s*quá",
    r"tệ.*nhất",
    r"đừng.*mua",
    r"không.*nên.*mua",
    r"rác.*quá",
    r"(tồi|tệ|kém).*chất\s*lượng",
    r"chất\s*lượng.*(tệ|kém)",
]

DEFAULT_LEAD_PATTERNS = [
    r"giá.*bao\s*nhiêu",
    r"bao\s*nhiêu.*tiền",
    r"mua.*ở\s*đâu",
    r"ở\s*đâu.*mua",
    r"test\s*drive",
    r"xin.*giá",
    r"cho.*xin.*giá",
    r"đặt.*mua",
    r"đặt.*cọc",
    r"mua.*ngay",
]

DEFAULT_SUPPORT_PATTERNS = [
    r"cách.*sạc",
    r"làm\s*sao.*sạc",
    r"showroom",
    r"đại\s*lý",
    r"bảo\s*hành",
    r"sửa\s*chữa",
    r"hướng\s*dẫn",
    r"cách.*sử\s*dụng",
    r"trung\s*tâm.*bảo\s*hành",
]

# Regex flags
REGEX_FLAGS_IGNORECASE = "IGNORECASE"

# File encoding
FILE_ENCODING_UTF8 = "utf-8"

__all__ = [
    "INTENT_CRISIS",
    "INTENT_SEEDING",
    "INTENT_SPAM",
    "INTENT_COMPLAINT",
    "INTENT_LEAD",
    "INTENT_SUPPORT",
    "INTENT_DISCUSSION",
    "PRIORITY_CRISIS",
    "PRIORITY_SEEDING",
    "PRIORITY_SPAM",
    "PRIORITY_COMPLAINT",
    "PRIORITY_LEAD",
    "PRIORITY_SUPPORT",
    "PRIORITY_DISCUSSION",
    "CONFIDENCE_BASE",
    "CONFIDENCE_INCREMENT",
    "CONFIDENCE_MAX",
    "DEFAULT_CONFIDENCE_THRESHOLD",
    "DEFAULT_PATTERNS_PATH",
    "DEFAULT_CRISIS_PATTERNS",
    "DEFAULT_SEEDING_PATTERNS",
    "DEFAULT_SPAM_PATTERNS",
    "DEFAULT_COMPLAINT_PATTERNS",
    "DEFAULT_LEAD_PATTERNS",
    "DEFAULT_SUPPORT_PATTERNS",
    "REGEX_FLAGS_IGNORECASE",
    "FILE_ENCODING_UTF8",
]
