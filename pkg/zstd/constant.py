DEFAULT_LEVEL = 2
DEFAULT_CHUNK_SIZE = 8192
ALGORITHM_NAME = "zstd"

# Compression Levels
LEVEL_NO_COMPRESSION = 0
LEVEL_FAST = 1
LEVEL_DEFAULT = 2
LEVEL_BEST = 3

# Zstd Native Levels Map
ZSTD_LEVEL_MAP = {
    LEVEL_NO_COMPRESSION: 0,
    LEVEL_FAST: 3,
    LEVEL_DEFAULT: 10,
    LEVEL_BEST: 19,
}

# Errors
ERROR_INVALID_LEVEL = "Invalid compression level: {level}. Must be 0-3."
ERROR_CHUNK_SIZE_POSITIVE = "chunk_size must be positive, got {size}"
ERROR_COMPRESSION_FAILED = "Zstd compression failed: {error}"
ERROR_DECOMPRESSION_FAILED = "Zstd decompression failed: {error}"
ERROR_STREAM_COMPRESSION_FAILED = "Zstd stream compression failed: {error}"
ERROR_STREAM_DECOMPRESSION_FAILED = "Zstd stream decompression failed: {error}"
ERROR_LIB_NOT_INSTALLED = "zstandard library is not installed"
