"""Constants for storage infrastructure.

These are fixed values that follow AWS S3/MinIO conventions
and should not be changed via configuration.
"""

# Compression metadata keys (stored as x-amz-meta-* headers in MinIO)
# Analytics service format (used for uploads)
METADATA_COMPRESSION_ALGORITHM = "x-amz-meta-compression-algorithm"
METADATA_COMPRESSION_LEVEL = "x-amz-meta-compression-level"
METADATA_ORIGINAL_SIZE = "x-amz-meta-original-size"
METADATA_COMPRESSED_SIZE = "x-amz-meta-compressed-size"

# Crawler service format (used for downloads - backward compatibility)
# Crawler uses "compressed: true" as the primary indicator
METADATA_COMPRESSED = "x-amz-meta-compressed"

# All possible metadata keys for compression detection (lowercase for comparison)
COMPRESSION_METADATA_KEYS = {
    "compressed": "x-amz-meta-compressed",
    "compression-algorithm": "x-amz-meta-compression-algorithm",
    "compression-level": "x-amz-meta-compression-level",
    "original-size": "x-amz-meta-original-size",
    "compressed-size": "x-amz-meta-compressed-size",
}
