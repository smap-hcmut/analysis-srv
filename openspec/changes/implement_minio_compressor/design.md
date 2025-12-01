# Design: MinIO Compression and Swagger Initialization

## Context

The Analytics Engine currently stores JSON data in MinIO, but files are compressed without automatic decompression support. The consumer service downloads these files and expects JSON format, causing failures. Additionally, the API service needs Swagger UI accessible at `/swagger/index.html` for testing endpoints.

## Goals / Non-Goals

### Goals
- Implement Zstd compression/decompression for MinIO storage
- Auto-detect and decompress compressed files on download
- Initialize Swagger UI at `/swagger/index.html` for API service
- Update consumer to handle decompressed JSON data
- Preserve compression metadata for monitoring

### Non-Goals
- Async upload with progress tracking (future enhancement)
- Multiple compression algorithms (Zstd only)
- Compression for upload operations (download decompression only for now)

## Decisions

### Decision: Use Zstd Compression Algorithm
**Rationale**: Zstd provides excellent compression ratios (60-95% for JSON) with good performance. It's widely supported and has Python bindings via `zstandard` package.

**Alternatives considered**:
- Gzip: Lower compression ratio, slower
- LZ4: Faster but lower compression ratio
- Brotli: Good ratio but less common

### Decision: Auto-Decompression on Download
**Rationale**: Transparent decompression simplifies consumer code - it doesn't need to know if data is compressed. Metadata detection ensures backward compatibility with uncompressed files.

**Alternatives considered**:
- Explicit decompression flag: More control but requires caller knowledge
- Separate decompress method: More explicit but less convenient

### Decision: Swagger UI at `/swagger/index.html`
**Rationale**: User requested specific path. FastAPI supports custom OpenAPI docs paths via `docs_url` parameter.

**Alternatives considered**:
- Default `/docs`: Already exists but user wants custom path
- Both paths: Redundant, choose one

### Decision: Compression Metadata in Object Metadata
**Rationale**: Store compression info (algorithm, level, sizes) in MinIO object metadata for monitoring and debugging. Uses `x-amz-meta-*` headers.

**Alternatives considered**:
- Separate metadata file: More complex, additional storage
- No metadata: Simpler but loses compression stats

## Risks / Trade-offs

### Risk: Backward Compatibility
**Mitigation**: Auto-detection checks metadata - if no compression metadata exists, treat as uncompressed. Existing uncompressed files continue to work.

### Risk: Decompression Performance
**Mitigation**: Zstd is fast. For large files, decompression overhead is minimal compared to network I/O. Profile if needed.

### Risk: Missing zstandard Package
**Mitigation**: Add to `pyproject.toml` dependencies. Document in README. Fail gracefully with clear error message.

### Trade-off: Compression Level
- Level 0: No compression (fastest, largest)
- Level 1: Fast compression (~50-70% reduction)
- Level 2: Balanced (default, ~70-85% reduction) ✅
- Level 3: Best compression (~85-95% reduction, slower)

**Decision**: Default to level 2 (balanced). Allow configuration override.

## Migration Plan

1. **Add dependencies**: `zstandard` package
2. **Update MinIO adapter**: Add compression/decompression methods
3. **Update consumer**: Use decompressed data
4. **Add Swagger route**: Configure FastAPI docs
5. **Add configuration**: Compression settings in `core/config.py`
6. **Test**: Verify backward compatibility with existing uncompressed files

**Rollback**: If issues occur, disable compression via `COMPRESSION_ENABLED=false`. Existing uncompressed files continue to work.

## Open Questions

- Should we compress on upload as well? (Currently only decompress on download)
  - **Answer**: Not in this change. Focus on download decompression first.

- Should we support multiple compression algorithms?
  - **Answer**: No. Zstd only for simplicity.

