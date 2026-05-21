from __future__ import annotations

import csv
import io

from internal.http.analytics_service import posts_to_csv, posts_to_svg


def test_posts_to_csv_exports_full_filtered_rows():
    body = posts_to_csv(
        [
            {
                "id": "m1",
                "platform": "youtube",
                "contentType": "comment",
                "author": "@user",
                "authorUsername": "user",
                "time": "2026-05-21T10:00:00Z",
                "sentiment": "negative",
                "sentimentScore": -0.5,
                "engagement": 220,
                "views": 0,
                "likes": 220,
                "comments": 0,
                "shares": 0,
                "sourceKind": "stalker",
                "dataSourceId": "ds1",
                "targetId": "target1",
                "url": "https://example.test/post",
                "keywords": ["shipper", "app"],
                "content": "Nội dung comment",
            }
        ]
    )

    rows = list(csv.DictReader(io.StringIO(body)))
    assert len(rows) == 1
    assert rows[0]["platform"] == "youtube"
    assert rows[0]["contentType"] == "comment"
    assert rows[0]["keywords"] == "shipper; app"
    assert rows[0]["content"] == "Nội dung comment"


def test_posts_to_svg_includes_all_rows_and_escapes_content():
    body = posts_to_svg(
        [
            {
                "platform": "youtube",
                "contentType": "comment",
                "author": "<script>",
                "time": "2026-05-21T10:00:00Z",
                "sentiment": "negative",
                "engagement": 220,
                "content": "A < B & C",
            }
        ],
        {"platform": "youtube", "sentiment": "negative"},
        total=1,
    )

    assert "<svg" in body
    assert "Rows: 1 of 1" in body
    assert "&lt;script&gt;" in body
    assert "A &lt; B &amp; C" in body
