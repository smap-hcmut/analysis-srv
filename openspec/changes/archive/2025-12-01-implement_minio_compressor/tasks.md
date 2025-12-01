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

- [x] 2.2 Update `download_json()` method
  - Download object from MinIO
  - Check metadata for compression flag
  - Auto-decompress if compressed
  - Parse JSON from decompressed data
  - Maintain backward compatibility (uncompressed files)

- [x] 2.3 Add compression metadata helpers
  - `_build_compression_metadata()` - Create metadata dict
  - `_parse_compression_metadata()` - Extract from object metadata

## 3. Swagger UI Initialization

- [x] 3.1 Update `internal/api/main.py`
  - Add Swagger UI route at `/swagger/index.html`
  - Configure FastAPI `docs_url` parameter
  - Ensure OpenAPI schema is accessible

- [x] 3.2 Verify Swagger UI accessibility
  - Test `/swagger/index.html` loads correctly
  - Verify all endpoints are documented
  - Test endpoint execution from Swagger UI

## 4. Consumer Decompression Integration

- [x] 4.1 Update `internal/consumers/main.py`
  - Ensure `minio_adapter.download_json()` uses decompression
  - Verify JSON parsing works with decompressed data
  - Add error handling for decompression failures

- [x] 4.2 Test consumer with compressed data
  - Create test compressed file in MinIO
  - Verify consumer processes correctly
  - Verify backward compatibility with uncompressed files

## 5. Testing

- [x] 5.1 Unit tests for compression/decompression
  - Test `_compress_data()` with various data sizes
  - Test `_decompress_data()` with compressed data
  - Test `_is_compressed()` metadata detection
  - Test backward compatibility (no metadata = uncompressed)

- [x] 5.2 Integration tests
  - Test MinIO download with compressed file
  - Test MinIO download with uncompressed file
  - Test consumer end-to-end with compressed data

- [x] 5.3 API service tests
  - Test Swagger UI at `/swagger/index.html`
  - Verify OpenAPI schema generation
  - Test endpoint execution from Swagger UI

## 6. Documentation

- [x] 6.1 Update README.md
  - Document compression configuration
  - Document Swagger UI access
  - Add compression level recommendations

- [x] 6.2 Add code docstrings
  - Document compression methods
  - Document metadata structure
  - Add usage examples

## 7. Validation

- [x] 7.1 Run linter and type checker
  - Fix any linting errors
  - Resolve type checking issues

- [x] 7.2 Run test suite
  - All unit tests pass
  - All integration tests pass
  - Coverage maintained or improved

- [x] 7.3 Manual verification
  - Start API service, verify Swagger UI accessible
  - Test consumer with compressed MinIO file
  - Verify backward compatibility

## 8. API Test JSON Format Validation

- [x] 8.1 Ensure API test endpoint accepts standard JSON format
  - Verify API test endpoint accepts JSON with `meta`, `content`, `interaction`, `author`, and `comments` sections
  - Test with sample JSON matching the format:
    - `meta` section with `id`, `platform`, `project_id`, `job_id`, `crawled_at`, `published_at`, `permalink`, `keyword_source`, `lang`, `region`, `fetch_status`, `fetch_error`
    - `content` section with `text`, `text_clean`, `transcription`, `transcription_language`, `transcription_summary`, `duration`, `audio_path`, `thumbnail`, `hashtags`, `tags_raw`
    - `interaction` section with `views`, `likes`, `comments_count`, `shares`, `saves`
    - `author` section with `id`, `name`, `username`, `followers`, `following`, `likes`, `videos`, `is_verified`, `bio`, `avatar_url`, `profile_url`
    - `comments` array with comment objects containing `id`, `parent_id`, `post_id`, `user`, `text`, `likes`, `replies_count`, `published_at`, `is_author`
  - Verify API processes the JSON correctly through the orchestrator
  - Test via Swagger UI at `/swagger/index.html` with the sample JSON
  - [x] 8.2 Example: cURL command for testing API with standard JSON format
    - Use the following cURL command to send a sample request to the API test endpoint (replace `<API_URL>` with your actual endpoint):

      ```bash
      curl -X POST <API_URL> \
        -H "Content-Type: application/json" \
        -d '{
          "meta": {
            "id": "7577034049470926087",
            "platform": "tiktok",
            "project_id": "proj_tet_2025",
            "job_id": "job-a31d2aba...",
            "crawled_at": "2025-11-28T20:20:54Z",
            "published_at": "2025-11-26T14:01:58Z",
            "permalink": "https://www.tiktok.com/@wrapstudio/video/757703...",
            "keyword_source": "vinfast",
            "lang": "vi",
            "region": "VN",
            "fetch_status": "success",
            "fetch_error": null
          },
          "content": {
            "text": "Vươn tầm thế giới chưa ae :)) cứ chê vin đi #tintuc24h",
            "text_clean": "Vươn tầm thế giới chưa anh em cứ chê vin đi",
            "transcription": "Xin chào các bạn, hôm nay...",
            "transcription_language": "vi",
            "transcription_summary": "Video nói về việc VinFast...",
            "duration": 19,
            "audio_path": "minio://audios/tiktok/2025/11/757703...mp3",
            "thumbnail": "minio://images/tiktok/2025/11/757703...jpg",
            "hashtags": ["tintuc24h", "tinnong", "vinfast"],
            "tags_raw": "#tintuc24h #tinnong #vinfast"
          },
          "interaction": {
            "views": 81100,
            "likes": 2553,
            "comments_count": 534,
            "shares": 74,
            "saves": 93
          },
          "author": {
            "id": "wrapstudio.tintuc24h",
            "name": "Wrap Studio Tin Tức 24h",
            "username": "wrapstudio.tintuc24h",
            "followers": 396,
            "following": 18,
            "likes": 8895,
            "videos": 43,
            "is_verified": false,
            "bio": "Cập nhật tin nóng về ô tô...",
            "avatar_url": "https://p16-sign-sg.tiktokcdn...",
            "profile_url": "https://www.tiktok.com/@wrapstudio.tintuc24h"
          },
          "comments": [
            {
              "id": "7577174763429872391",
              "parent_id": null,
              "post_id": "7577034049470926087",
              "user": {
                "id": "user_thai_pho",
                "name": "Thái phở"
              },
              "text": "Mỹ nó đang chạy ngoài đường rồi...",
              "likes": 211,
              "replies_count": 79,
              "published_at": "2025-11-27T06:08:19Z",
              "is_author": false
            }
          ]
        }'
      ```
    - Confirm: API responds with correct processing result and no validation errors for this sample input.
