# Tasks: Implement MinIO Compression and Swagger Initialization

## 1. Dependencies and Configuration

- [x] 1.1 Add `zstandard` package to `pyproject.toml`
  - Add dependency: `zstandard>=0.22.0`
  - Update lock file with `uv lock`

- [x] 1.2 Add compression configuration to `core/config.py`
  - Add `compression_enabled: bool = True`
  - Add `compression_default_level: int = 2`
  - Add `compression_algorithm: str = "zstd"`
  - Add `compression_min_size_bytes: int = 1024`

## 2. MinIO Storage Compression Implementation

- [x] 2.1 Update `infrastructure/storage/minio_client.py`
  - Add `_compress_data()` method for Zstd compression
  - Add `_decompress_data()` method for Zstd decompression
  - Add `_is_compressed()` method to check metadata
  - Add `_get_compression_metadata()` helper

- [ ] 2.2 Update `download_json()` method
  - Download object from MinIO
  - Check metadata for compression flag
  - Auto-decompress if compressed
  - Parse JSON from decompressed data
  - Maintain backward compatibility (uncompressed files)

- [ ] 2.3 Add compression metadata helpers
  - `_build_compression_metadata()` - Create metadata dict
  - `_parse_compression_metadata()` - Extract from object metadata

## 3. Swagger UI Initialization

- [ ] 3.1 Update `internal/api/main.py`
  - Add Swagger UI route at `/swagger/index.html`
  - Configure FastAPI `docs_url` parameter
  - Ensure OpenAPI schema is accessible

- [ ] 3.2 Verify Swagger UI accessibility
  - Test `/swagger/index.html` loads correctly
  - Verify all endpoints are documented
  - Test endpoint execution from Swagger UI

## 4. Consumer Decompression Integration

- [ ] 4.1 Update `internal/consumers/main.py`
  - Ensure `minio_adapter.download_json()` uses decompression
  - Verify JSON parsing works with decompressed data
  - Add error handling for decompression failures

- [ ] 4.2 Test consumer with compressed data
  - Create test compressed file in MinIO
  - Verify consumer processes correctly
  - Verify backward compatibility with uncompressed files

## 5. Testing

- [ ] 5.1 Unit tests for compression/decompression
  - Test `_compress_data()` with various data sizes
  - Test `_decompress_data()` with compressed data
  - Test `_is_compressed()` metadata detection
  - Test backward compatibility (no metadata = uncompressed)

- [ ] 5.2 Integration tests
  - Test MinIO download with compressed file
  - Test MinIO download with uncompressed file
  - Test consumer end-to-end with compressed data

- [ ] 5.3 API service tests
  - Test Swagger UI at `/swagger/index.html`
  - Verify OpenAPI schema generation
  - Test endpoint execution from Swagger UI

## 6. Documentation

- [ ] 6.1 Update README.md
  - Document compression configuration
  - Document Swagger UI access
  - Add compression level recommendations

- [ ] 6.2 Add code docstrings
  - Document compression methods
  - Document metadata structure
  - Add usage examples

## 7. Validation

- [ ] 7.1 Run linter and type checker
  - Fix any linting errors
  - Resolve type checking issues

- [ ] 7.2 Run test suite
  - All unit tests pass
  - All integration tests pass
  - Coverage maintained or improved

- [ ] 7.3 Manual verification
  - Start API service, verify Swagger UI accessible
  - Test consumer with compressed MinIO file
  - Verify backward compatibility

