#!/bin/bash
# Example cURL command for testing API with standard JSON format
# This script demonstrates how to send a sample request to the API test endpoint
#
# Usage:
#   1. Start the API server: make run-api (or uvicorn internal.api.main:app --reload)
#   2. Run this script: ./examples/api_test_curl_example.sh
#
# The API endpoint accepts JSON with the following structure:
# - meta: Post metadata (id, platform, project_id, job_id, crawled_at, published_at, permalink, keyword_source, lang, region, fetch_status, fetch_error)
# - content: Post content (text, text_clean, transcription, transcription_language, transcription_summary, duration, audio_path, thumbnail, hashtags, tags_raw)
# - interaction: Engagement metrics (views, likes, comments_count, shares, saves)
# - author: Author information (id, name, username, followers, following, likes, videos, is_verified, bio, avatar_url, profile_url)
# - comments: Array of comment objects (id, parent_id, post_id, user, text, likes, replies_count, published_at, is_author)

API_URL="${API_URL:-http://localhost:8000}"

echo "Testing API endpoint: ${API_URL}/test/analytics"
echo "================================================"

curl -X POST "${API_URL}/test/analytics" \
  -H "Content-Type: application/json" \
  -d '{
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
      "fetch_error": null
    },
    "content": {
      "text": "Vươn tầm thế giới chưa ae :)) cứ chê vin đi #tintuc24h",
      "text_clean": "Vươn tầm thế giới chưa anh em cứ chê vin đi",
      "transcription": "Xin chào các bạn, hôm nay chúng ta sẽ nói về VinFast vươn ra thế giới",
      "transcription_language": "vi",
      "transcription_summary": "Video nói về việc VinFast vươn ra thế giới và nhận được nhiều phản hồi tích cực",
      "duration": 19,
      "audio_path": "minio://audios/tiktok/2025/11/7577034049470926087.mp3",
      "thumbnail": "minio://images/tiktok/2025/11/7577034049470926087.jpg",
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
      "bio": "Cập nhật tin nóng về ô tô, xe máy và công nghệ",
      "avatar_url": "https://p16-sign-sg.tiktokcdn.com/avatar.jpg",
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
        "text": "Mỹ nó đang chạy ngoài đường rồi còn gì",
        "likes": 211,
        "replies_count": 79,
        "published_at": "2025-11-27T06:08:19Z",
        "is_author": false
      }
    ]
  }'

echo ""
echo ""
echo "================================================"
echo "Test completed. Check the response above."
echo ""
echo "You can also test via Swagger UI at: ${API_URL}/swagger/index.html"
