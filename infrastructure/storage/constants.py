"""Constants for storage infrastructure.

These are fixed values that follow AWS S3/MinIO conventions
and should not be changed via configuration.
"""

# Compression metadata keys (stored as x-amz-meta-* headers in MinIO)
METADATA_COMPRESSION_ALGORITHM = "x-amz-meta-compression-algorithm"
METADATA_COMPRESSION_LEVEL = "x-amz-meta-compression-level"
METADATA_ORIGINAL_SIZE = "x-amz-meta-original-size"
METADATA_COMPRESSED_SIZE = "x-amz-meta-compressed-size"
