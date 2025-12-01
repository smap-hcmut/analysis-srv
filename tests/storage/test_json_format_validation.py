"""Test JSON format validation for API test endpoint.

This test validates that the API test endpoint accepts the standard JSON format
with all required fields as specified in the master-proposal.md.
"""

import pytest
import httpx
from internal.api.main import app


@pytest.fixture
def anyio_backend():
    """Use asyncio backend only."""
    return "asyncio"


@pytest.mark.anyio
async def test_api_accepts_standard_json_format(anyio_backend):
    """Test that API test endpoint accepts standard JSON format with all required fields."""
    # Sample JSON matching the standard format
    sample_json = {
        "meta": {
            "id": "7577034049470926087",
            "platform": "tiktok",
            "project_id": "proj_tet_2025",
            "job_id": "job-a31d2aba-1234-5678-9abc-def012345678",
            "crawled_at": "2025-11-28T20:20:54Z",
            "published_at": "2025-11-26T14:01:58Z",
            "permalink": "https://www.tiktok.com/@wrapstudio/video/7577034049470926087",
            "keyword_source": "vinfast",
            "lang": "vi",
            "region": "VN",
            "fetch_status": "success",
            "fetch_error": None,
        },
        "content": {
            "text": "Vươn tầm thế giới chưa ae :)) cứ chê vin đi #tintuc24h",
            "text_clean": "Vươn tầm thế giới chưa anh em cứ chê vin đi",
            "transcription": "Xin chào các bạn, hôm nay chúng ta sẽ nói về VinFast",
            "transcription_language": "vi",
            "transcription_summary": "Video nói về việc VinFast vươn ra thế giới",
            "duration": 19,
            "audio_path": "minio://audios/tiktok/2025/11/7577034049470926087.mp3",
            "thumbnail": "minio://images/tiktok/2025/11/7577034049470926087.jpg",
            "hashtags": ["tintuc24h", "tinnong", "vinfast"],
            "tags_raw": "#tintuc24h #tinnong #vinfast",
        },
        "interaction": {
            "views": 81100,
            "likes": 2553,
            "comments_count": 534,
            "shares": 74,
            "saves": 93,
        },
        "author": {
            "id": "wrapstudio.tintuc24h",
            "name": "Wrap Studio Tin Tức 24h",
            "username": "wrapstudio.tintuc24h",
            "followers": 396,
            "following": 18,
            "likes": 8895,
            "videos": 43,
            "is_verified": False,
            "bio": "Cập nhật tin nóng về ô tô, xe máy và công nghệ",
            "avatar_url": "https://p16-sign-sg.tiktokcdn.com/avatar.jpg",
            "profile_url": "https://www.tiktok.com/@wrapstudio.tintuc24h",
        },
        "comments": [
            {
                "id": "7577174763429872391",
                "parent_id": None,
                "post_id": "7577034049470926087",
                "user": {"id": "user_thai_pho", "name": "Thái phở"},
                "text": "Mỹ nó đang chạy ngoài đường rồi còn gì",
                "likes": 211,
                "replies_count": 79,
                "published_at": "2025-11-27T06:08:19Z",
                "is_author": False,
            }
        ],
    }

    # Use httpx.ASGITransport to test the app directly
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/test/analytics", json=sample_json)

        # Verify response
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

        # Verify response structure
        data = response.json()
        assert "post_id" in data
        assert data["post_id"] == "7577034049470926087"
        assert "preprocessing" in data
        assert "keywords" in data
        assert "sentiment" in data
        assert "metadata" in data

        print("✓ API test endpoint accepts standard JSON format")
        print(f"✓ Response: {data}")


@pytest.mark.anyio
@pytest.mark.skip(reason="Orchestrator endpoint has internal service dependencies that may not be available in test environment")
async def test_api_accepts_orchestrator_json_format(anyio_backend):
    """Test that orchestrator endpoint accepts standard JSON format."""
    sample_json = {
        "meta": {
            "id": "7577034049470926087",
            "platform": "tiktok",
            "project_id": "proj_tet_2025",
            "job_id": "job-a31d2aba-1234-5678-9abc-def012345678",
            "crawled_at": "2025-11-28T20:20:54Z",
            "published_at": "2025-11-26T14:01:58Z",
            "permalink": "https://www.tiktok.com/@wrapstudio/video/7577034049470926087",
            "keyword_source": "vinfast",
            "lang": "vi",
            "region": "VN",
            "fetch_status": "success",
            "fetch_error": None,
        },
        "content": {
            "text": "Vươn tầm thế giới chưa ae :)) cứ chê vin đi #tintuc24h",
            "text_clean": "Vươn tầm thế giới chưa anh em cứ chê vin đi",
            "transcription": "Xin chào các bạn, hôm nay chúng ta sẽ nói về VinFast",
            "transcription_language": "vi",
            "transcription_summary": "Video nói về việc VinFast vươn ra thế giới",
            "duration": 19,
            "audio_path": "minio://audios/tiktok/2025/11/7577034049470926087.mp3",
            "thumbnail": "minio://images/tiktok/2025/11/7577034049470926087.jpg",
            "hashtags": ["tintuc24h", "tinnong", "vinfast"],
            "tags_raw": "#tintuc24h #tinnong #vinfast",
        },
        "interaction": {
            "views": 81100,
            "likes": 2553,
            "comments_count": 534,
            "shares": 74,
            "saves": 93,
        },
        "author": {
            "id": "wrapstudio.tintuc24h",
            "name": "Wrap Studio Tin Tức 24h",
            "username": "wrapstudio.tintuc24h",
            "followers": 396,
            "following": 18,
            "likes": 8895,
            "videos": 43,
            "is_verified": False,
            "bio": "Cập nhật tin nóng về ô tô, xe máy và công nghệ",
            "avatar_url": "https://p16-sign-sg.tiktokcdn.com/avatar.jpg",
            "profile_url": "https://www.tiktok.com/@wrapstudio.tintuc24h",
        },
        "comments": [
            {
                "id": "7577174763429872391",
                "parent_id": None,
                "post_id": "7577034049470926087",
                "user": {"id": "user_thai_pho", "name": "Thái phở"},
                "text": "Mỹ nó đang chạy ngoài đường rồi còn gì",
                "likes": 211,
                "replies_count": 79,
                "published_at": "2025-11-27T06:08:19Z",
                "is_author": False,
            }
        ],
    }

    # Use httpx.ASGITransport to test the app directly
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/dev/process-post-direct", json=sample_json)

        # Verify response
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

        # Verify response structure
        data = response.json()
        assert "status" in data
        assert "data" in data

        print("✓ Orchestrator endpoint accepts standard JSON format")
        print(f"✓ Response status: {data['status']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
