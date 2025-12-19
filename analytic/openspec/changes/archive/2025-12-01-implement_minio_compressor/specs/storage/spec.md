# storage Specification

## ADDED Requirements

### Requirement: MinIO Compression Support

The Analytics Engine SHALL support Zstd compression for MinIO storage operations to reduce storage costs and improve transfer efficiency.

**Rationale**: JSON data compresses well with Zstd (60-95% reduction), significantly reducing storage costs and network transfer time.

#### Scenario: Compress Data Before Storage

**Given** compression is enabled in configuration  
**When** data is prepared for MinIO upload  
**Then** the system SHALL compress data using Zstd algorithm  
**And** compression metadata SHALL be stored in object metadata  
**And** compression level SHALL be configurable (0-3)

#### Scenario: Compression Configuration

**Given** compression settings are configured  
**When** compression is enabled (`COMPRESSION_ENABLED=true`)  
**Then** default compression level SHALL be 2 (balanced)  
**And** compression algorithm SHALL be Zstd  
**And** files smaller than `COMPRESSION_MIN_SIZE_BYTES` SHALL not be compressed

---

### Requirement: Auto-Decompression on Download

The Analytics Engine SHALL automatically decompress compressed files when downloading from MinIO, transparently handling both compressed and uncompressed data.

**Rationale**: Consumers and API services should not need to know if data is compressed. Auto-decompression simplifies code and ensures backward compatibility.

#### Scenario: Decompress Compressed File

**Given** a compressed file exists in MinIO with compression metadata  
**When** `download_json()` is called  
**Then** the system SHALL detect compression from metadata  
**And** the system SHALL automatically decompress the data  
**And** the system SHALL return decompressed JSON data  
**And** the operation SHALL be transparent to the caller

#### Scenario: Handle Uncompressed File

**Given** an uncompressed file exists in MinIO (no compression metadata)  
**When** `download_json()` is called  
**Then** the system SHALL detect no compression metadata  
**And** the system SHALL return data without decompression  
**And** backward compatibility SHALL be maintained

#### Scenario: Decompression Failure Handling

**Given** a file has compression metadata but decompression fails  
**When** `download_json()` attempts to decompress  
**Then** the system SHALL raise a clear error indicating decompression failure  
**And** the error SHALL include the object path and failure reason

---

### Requirement: Compression Metadata Preservation

The Analytics Engine SHALL store compression metadata in MinIO object metadata for monitoring, debugging, and transparency.

**Rationale**: Compression metadata (algorithm, level, sizes, ratio) enables monitoring storage savings and debugging compression issues.

#### Scenario: Store Compression Metadata

**Given** data is compressed before upload  
**When** object is stored in MinIO  
**Then** metadata SHALL include `x-amz-meta-compressed: "true"`  
**And** metadata SHALL include `x-amz-meta-compression-algorithm: "zstd"`  
**And** metadata SHALL include `x-amz-meta-compression-level: "<level>"`  
**And** metadata SHALL include `x-amz-meta-original-size: "<bytes>"`  
**And** metadata SHALL include `x-amz-meta-compressed-size: "<bytes>"`  
**And** metadata SHALL include `x-amz-meta-compression-ratio: "<ratio>"`

#### Scenario: Read Compression Metadata

**Given** a compressed object exists in MinIO  
**When** object metadata is retrieved  
**Then** compression metadata SHALL be accessible  
**And** metadata SHALL enable calculation of storage savings

---

### Requirement: Compression Configuration

The Analytics Engine SHALL provide configuration settings for compression behavior.

**Rationale**: Different use cases require different compression levels. Configuration enables optimization for performance vs. storage savings.

#### Scenario: Enable Compression

**Given** `COMPRESSION_ENABLED=true` in configuration  
**When** MinIO storage operations are performed  
**Then** compression SHALL be applied according to settings

#### Scenario: Disable Compression

**Given** `COMPRESSION_ENABLED=false` in configuration  
**When** MinIO storage operations are performed  
**Then** compression SHALL be skipped  
**And** files SHALL be stored uncompressed

#### Scenario: Configure Compression Level

**Given** `COMPRESSION_DEFAULT_LEVEL` is set (0-3)  
**When** compression is applied  
**Then** the specified level SHALL be used  
**And** level 0 SHALL mean no compression  
**And** level 1 SHALL mean fast compression  
**And** level 2 SHALL mean balanced compression (default)  
**And** level 3 SHALL mean best compression

