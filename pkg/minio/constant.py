# Analytics service format (used for uploads)
METADATA_COMPRESSION_ALGORITHM = "x-amz-meta-compression-algorithm"
METADATA_COMPRESSION_LEVEL = "x-amz-meta-compression-level"
METADATA_ORIGINAL_SIZE = "x-amz-meta-original-size"
METADATA_COMPRESSED_SIZE = "x-amz-meta-compressed-size"

# Crawler service format
METADATA_COMPRESSED = "x-amz-meta-compressed"

COMPRESSION_METADATA_KEYS = {
    "compressed": "x-amz-meta-compressed",
    "compression-algorithm": "x-amz-meta-compression-algorithm",
    "compression-level": "x-amz-meta-compression-level",
    "original-size": "x-amz-meta-original-size",
    "compressed-size": "x-amz-meta-compressed-size",
}
