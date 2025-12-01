# Change: Implement MinIO Compression and Swagger Initialization

## Why

Currently, files stored in MinIO are compressed/zipped, but the system lacks automatic decompression when downloading. This causes issues when the consumer service tries to process messages - it receives compressed data that cannot be directly parsed as JSON. Additionally, the API service needs Swagger UI initialized at `/swagger/index.html` for API testing and documentation.

**Problem**: 
- MinIO downloads return compressed data that cannot be directly parsed
- Consumer service fails when processing compressed messages
- API service lacks accessible Swagger UI for endpoint testing

**Solution**:
- Implement Zstd compression/decompression in MinIO storage adapter
- Add auto-decompression on download with metadata detection
- Initialize Swagger UI at `/swagger/index.html` for API service
- Update consumer to handle decompressed JSON format

## What Changes

- **ADDED**: MinIO storage compression/decompression capability using Zstd
  - Compression on upload with configurable levels (0-3)
  - Auto-decompression on download with metadata detection
  - Compression metadata preservation (original size, compressed size, ratio)
  
- **ADDED**: Swagger UI initialization at `/swagger/index.html`
  - FastAPI OpenAPI docs accessible at custom path
  - API service startup includes Swagger UI configuration
  
- **MODIFIED**: Consumer message processing
  - Consumer automatically decompresses MinIO downloads
  - JSON parsing works with decompressed data
  - Proper error handling for decompression failures

- **ADDED**: Configuration settings for compression
  - `COMPRESSION_ENABLED` - Enable/disable compression
  - `COMPRESSION_DEFAULT_LEVEL` - Default compression level (0-3)
  - `COMPRESSION_ALGORITHM` - Compression algorithm (zstd)
  - `COMPRESSION_MIN_SIZE_BYTES` - Minimum size to compress

## Impact

- **Affected specs**: 
  - `storage` (new capability)
  - `test_api` (Swagger UI path)
  - `service_lifecycle` (consumer decompression)
  
- **Affected code**:
  - `infrastructure/storage/minio_client.py` - Add compression/decompression
  - `internal/api/main.py` - Add Swagger UI route
  - `internal/consumers/main.py` - Handle decompressed data
  - `core/config.py` - Add compression settings
  
- **Dependencies**:
  - `zstandard` Python package for Zstd compression
  - FastAPI OpenAPI/Swagger UI (already available)

**Related Docs**: `documents/term.md` - MinIO Compression & Async Upload guide

