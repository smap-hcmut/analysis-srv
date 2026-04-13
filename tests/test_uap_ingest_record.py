"""Tests for UAPRecord.from_ingest_record() — ingest-srv flat wire format parser.

Covers:
  - Happy path: all fields fully populated
  - Required-field validation (missing project_id, missing uap_id)
  - Engagement integer coercion (None, string, float)
  - crawl_keyword → keywords_matched list
  - media[] → content.attachments[] including download_url fallback
  - domain_type_code propagated to both UAPRecord.domain_type_code and raw
  - hierarchy / platform_meta preserved in .raw
  - task_id preserved in .raw
  - doc_type defaults to "post" and is lowercased
  - uap_version is always empty string (ingest-srv does not emit it)
  - Minimal record (only required fields) parses without error
"""

from __future__ import annotations

import pytest

from internal.model.uap import ErrUAPValidation, UAPRecord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def make_full_envelope(
    *,
    project_id: str = "proj-001",
    uap_id: str = "uap-abc123",
    uap_type: str = "POST",
    platform: str = "facebook",
    origin_id: str = "fb-99",
    url: str = "https://fb.com/posts/99",
    task_id: str = "task-xyz",
    text: str = "Xe VinFast rất tốt!",
    language: str = "vi",
    posted_at: str = "2024-01-01T00:00:00Z",
    ingested_at: str = "2024-01-01T01:00:00Z",
    author_id: str = "user-1",
    nickname: str = "Người dùng A",
    username: str = "nguoidunga",
    avatar: str = "https://cdn.example.com/avatar.jpg",
    is_verified: bool = True,
    parent_id: str = "uap-parent",
    likes: int = 100,
    comments_count: int = 20,
    shares: int = 5,
    views: int = 1000,
    saves: int = 3,
    domain_type_code: str = "vinfast",
    crawl_keyword: str = "vinfast vf8",
) -> dict:
    return {
        "identity": {
            "uap_id": uap_id,
            "uap_type": uap_type,
            "platform": platform,
            "origin_id": origin_id,
            "url": url,
            "task_id": task_id,
            "project_id": project_id,
        },
        "hierarchy": {
            "parent_id": parent_id,
            "root_id": "uap-root",
            "depth": 1,
        },
        "content": {
            "text": text,
            "language": language,
        },
        "author": {
            "id": author_id,
            "nickname": nickname,
            "username": username,
            "avatar": avatar,
            "is_verified": is_verified,
        },
        "engagement": {
            "likes": likes,
            "comments_count": comments_count,
            "shares": shares,
            "views": views,
            "saves": saves,
        },
        "media": [
            {"type": "image", "url": "https://cdn.example.com/img.jpg"},
        ],
        "temporal": {
            "posted_at": posted_at,
            "ingested_at": ingested_at,
        },
        "domain_type_code": domain_type_code,
        "crawl_keyword": crawl_keyword,
        "platform_meta": {"extra_field": "some_value"},
    }


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestFromIngestRecordHappyPath:
    def test_event_id_equals_uap_id(self):
        rec = UAPRecord.from_ingest_record(make_full_envelope())
        assert rec.event_id == "uap-abc123"

    def test_uap_version_is_empty(self):
        """ingest-srv does not emit uap_version; field must be empty."""
        rec = UAPRecord.from_ingest_record(make_full_envelope())
        assert rec.uap_version == ""

    def test_project_id_mapped(self):
        rec = UAPRecord.from_ingest_record(make_full_envelope())
        assert rec.ingest.project_id == "proj-001"

    def test_source_type_from_platform(self):
        rec = UAPRecord.from_ingest_record(make_full_envelope(platform="tiktok"))
        assert rec.ingest.source.source_type == "tiktok"

    def test_source_id_from_origin_id(self):
        rec = UAPRecord.from_ingest_record(make_full_envelope(origin_id="tt-55"))
        assert rec.ingest.source.source_id == "tt-55"

    def test_received_at_from_ingested_at(self):
        rec = UAPRecord.from_ingest_record(
            make_full_envelope(ingested_at="2024-06-15T12:00:00Z")
        )
        assert rec.ingest.batch.received_at == "2024-06-15T12:00:00Z"

    def test_mapping_id_from_task_id(self):
        rec = UAPRecord.from_ingest_record(make_full_envelope(task_id="task-999"))
        assert rec.ingest.trace.mapping_id == "task-999"

    def test_doc_id_equals_uap_id(self):
        rec = UAPRecord.from_ingest_record(make_full_envelope())
        assert rec.content.doc_id == "uap-abc123"

    def test_doc_type_lowercased(self):
        rec = UAPRecord.from_ingest_record(make_full_envelope(uap_type="COMMENT"))
        assert rec.content.doc_type == "comment"

    def test_doc_type_defaults_to_post_when_empty(self):
        env = make_full_envelope()
        env["identity"]["uap_type"] = ""
        rec = UAPRecord.from_ingest_record(env)
        assert rec.content.doc_type == "post"

    def test_content_text(self):
        rec = UAPRecord.from_ingest_record(make_full_envelope(text="Hello world"))
        assert rec.content.text == "Hello world"

    def test_content_url(self):
        rec = UAPRecord.from_ingest_record(
            make_full_envelope(url="https://example.com/post/1")
        )
        assert rec.content.url == "https://example.com/post/1"

    def test_content_language(self):
        rec = UAPRecord.from_ingest_record(make_full_envelope(language="en"))
        assert rec.content.language == "en"

    def test_content_published_at(self):
        rec = UAPRecord.from_ingest_record(
            make_full_envelope(posted_at="2024-03-01T08:00:00Z")
        )
        assert rec.content.published_at == "2024-03-01T08:00:00Z"

    def test_author_id(self):
        rec = UAPRecord.from_ingest_record(make_full_envelope(author_id="u-777"))
        assert rec.content.author.author_id == "u-777"

    def test_author_display_name_from_nickname(self):
        rec = UAPRecord.from_ingest_record(make_full_envelope(nickname="Jane"))
        assert rec.content.author.display_name == "Jane"

    def test_author_username(self):
        rec = UAPRecord.from_ingest_record(make_full_envelope(username="janesmith"))
        assert rec.content.author.username == "janesmith"

    def test_author_avatar_url(self):
        rec = UAPRecord.from_ingest_record(
            make_full_envelope(avatar="https://cdn.example.com/j.jpg")
        )
        assert rec.content.author.avatar_url == "https://cdn.example.com/j.jpg"

    def test_author_is_verified(self):
        rec = UAPRecord.from_ingest_record(make_full_envelope(is_verified=True))
        assert rec.content.author.is_verified is True

    def test_parent_id_from_hierarchy(self):
        rec = UAPRecord.from_ingest_record(make_full_envelope(parent_id="uap-p1"))
        assert rec.content.parent.parent_id == "uap-p1"

    def test_engagement_like_count(self):
        rec = UAPRecord.from_ingest_record(make_full_envelope(likes=42))
        assert rec.signals.engagement.like_count == 42

    def test_engagement_comment_count(self):
        rec = UAPRecord.from_ingest_record(make_full_envelope(comments_count=7))
        assert rec.signals.engagement.comment_count == 7

    def test_engagement_share_count(self):
        rec = UAPRecord.from_ingest_record(make_full_envelope(shares=3))
        assert rec.signals.engagement.share_count == 3

    def test_engagement_view_count(self):
        rec = UAPRecord.from_ingest_record(make_full_envelope(views=9999))
        assert rec.signals.engagement.view_count == 9999

    def test_engagement_save_count(self):
        rec = UAPRecord.from_ingest_record(make_full_envelope(saves=11))
        assert rec.signals.engagement.save_count == 11

    def test_domain_type_code_on_record(self):
        rec = UAPRecord.from_ingest_record(
            make_full_envelope(domain_type_code="vinfast")
        )
        assert rec.domain_type_code == "vinfast"

    def test_domain_type_code_in_raw(self):
        rec = UAPRecord.from_ingest_record(
            make_full_envelope(domain_type_code="vinfast")
        )
        assert rec.raw.get("domain_type_code") == "vinfast"

    def test_hierarchy_preserved_in_raw(self):
        rec = UAPRecord.from_ingest_record(make_full_envelope())
        assert rec.raw.get("hierarchy") == {
            "parent_id": "uap-parent",
            "root_id": "uap-root",
            "depth": 1,
        }

    def test_platform_meta_preserved_in_raw(self):
        rec = UAPRecord.from_ingest_record(make_full_envelope())
        assert rec.raw.get("platform_meta") == {"extra_field": "some_value"}

    def test_task_id_preserved_in_raw(self):
        rec = UAPRecord.from_ingest_record(make_full_envelope(task_id="task-xyz"))
        assert rec.raw.get("task_id") == "task-xyz"

    def test_crawl_keyword_becomes_keywords_matched_list(self):
        rec = UAPRecord.from_ingest_record(
            make_full_envelope(crawl_keyword="vinfast vf8")
        )
        assert rec.context.keywords_matched == ["vinfast vf8"]


# ---------------------------------------------------------------------------
# Media / attachments
# ---------------------------------------------------------------------------


class TestFromIngestRecordAttachments:
    def test_media_url_mapped_to_attachment(self):
        env = make_full_envelope()
        env["media"] = [{"type": "image", "url": "https://img.example.com/a.jpg"}]
        rec = UAPRecord.from_ingest_record(env)
        assert len(rec.content.attachments) == 1
        att = rec.content.attachments[0]
        assert att.type == "image"
        assert att.url == "https://img.example.com/a.jpg"

    def test_media_download_url_fallback(self):
        """If url is absent/empty, fall back to download_url."""
        env = make_full_envelope()
        env["media"] = [
            {"type": "video", "url": "", "download_url": "https://dl.example.com/v.mp4"}
        ]
        rec = UAPRecord.from_ingest_record(env)
        assert rec.content.attachments[0].url == "https://dl.example.com/v.mp4"

    def test_multiple_media_items(self):
        env = make_full_envelope()
        env["media"] = [
            {"type": "image", "url": "https://img.example.com/1.jpg"},
            {"type": "image", "url": "https://img.example.com/2.jpg"},
            {"type": "video", "url": "https://vid.example.com/v.mp4"},
        ]
        rec = UAPRecord.from_ingest_record(env)
        assert len(rec.content.attachments) == 3

    def test_empty_media_list(self):
        env = make_full_envelope()
        env["media"] = []
        rec = UAPRecord.from_ingest_record(env)
        assert rec.content.attachments == []

    def test_non_dict_media_items_skipped(self):
        env = make_full_envelope()
        env["media"] = [
            "not-a-dict",
            None,
            {"type": "image", "url": "https://img.example.com/ok.jpg"},
        ]
        rec = UAPRecord.from_ingest_record(env)
        assert len(rec.content.attachments) == 1


# ---------------------------------------------------------------------------
# Engagement coercion edge cases
# ---------------------------------------------------------------------------


class TestFromIngestRecordEngagementCoercion:
    def test_none_engagement_values_default_to_zero(self):
        """_safe_int(None) returns the default (0), not None."""
        env = make_full_envelope()
        env["engagement"] = {"likes": None, "comments_count": None}
        rec = UAPRecord.from_ingest_record(env)
        assert rec.signals.engagement.like_count == 0
        assert rec.signals.engagement.comment_count == 0

    def test_string_engagement_coerced(self):
        env = make_full_envelope()
        env["engagement"] = {"likes": "50", "comments_count": "10"}
        rec = UAPRecord.from_ingest_record(env)
        assert rec.signals.engagement.like_count == 50
        assert rec.signals.engagement.comment_count == 10

    def test_float_engagement_truncated(self):
        env = make_full_envelope()
        env["engagement"] = {"likes": 3.9}
        rec = UAPRecord.from_ingest_record(env)
        assert rec.signals.engagement.like_count == 3

    def test_missing_engagement_block_defaults_to_zero(self):
        """Absent engagement block → _safe_int(None) for each field → 0."""
        env = make_full_envelope()
        del env["engagement"]
        rec = UAPRecord.from_ingest_record(env)
        assert rec.signals.engagement.like_count == 0
        assert rec.signals.engagement.view_count == 0


# ---------------------------------------------------------------------------
# Optional fields absent
# ---------------------------------------------------------------------------


class TestFromIngestRecordOptionalAbsent:
    def test_empty_crawl_keyword_gives_empty_list(self):
        env = make_full_envelope(crawl_keyword="")
        rec = UAPRecord.from_ingest_record(env)
        assert rec.context.keywords_matched == []

    def test_absent_crawl_keyword_gives_empty_list(self):
        env = make_full_envelope()
        del env["crawl_keyword"]
        rec = UAPRecord.from_ingest_record(env)
        assert rec.context.keywords_matched == []

    def test_absent_domain_type_code_defaults_to_empty(self):
        env = make_full_envelope()
        del env["domain_type_code"]
        rec = UAPRecord.from_ingest_record(env)
        assert rec.domain_type_code == ""
        assert "domain_type_code" not in rec.raw

    def test_absent_platform_meta_not_in_raw(self):
        env = make_full_envelope()
        del env["platform_meta"]
        rec = UAPRecord.from_ingest_record(env)
        assert "platform_meta" not in rec.raw

    def test_absent_hierarchy_not_in_raw(self):
        env = make_full_envelope()
        del env["hierarchy"]
        rec = UAPRecord.from_ingest_record(env)
        assert "hierarchy" not in rec.raw

    def test_absent_task_id_not_in_raw(self):
        env = make_full_envelope()
        del env["identity"]["task_id"]
        rec = UAPRecord.from_ingest_record(env)
        assert "task_id" not in rec.raw

    def test_absent_author_block(self):
        env = make_full_envelope()
        del env["author"]
        rec = UAPRecord.from_ingest_record(env)
        assert rec.content.author.author_id is None
        assert rec.content.author.is_verified is False


# ---------------------------------------------------------------------------
# Required-field validation
# ---------------------------------------------------------------------------


class TestFromIngestRecordValidation:
    def test_missing_project_id_raises(self):
        env = make_full_envelope()
        del env["identity"]["project_id"]
        with pytest.raises(ErrUAPValidation, match="project_id"):
            UAPRecord.from_ingest_record(env)

    def test_empty_project_id_raises(self):
        env = make_full_envelope()
        env["identity"]["project_id"] = ""
        with pytest.raises(ErrUAPValidation, match="project_id"):
            UAPRecord.from_ingest_record(env)

    def test_missing_uap_id_raises(self):
        env = make_full_envelope()
        del env["identity"]["uap_id"]
        with pytest.raises(ErrUAPValidation, match="uap_id"):
            UAPRecord.from_ingest_record(env)

    def test_empty_uap_id_raises(self):
        env = make_full_envelope()
        env["identity"]["uap_id"] = ""
        with pytest.raises(ErrUAPValidation, match="uap_id"):
            UAPRecord.from_ingest_record(env)

    def test_missing_identity_block_raises(self):
        env = make_full_envelope()
        del env["identity"]
        with pytest.raises(ErrUAPValidation):
            UAPRecord.from_ingest_record(env)


# ---------------------------------------------------------------------------
# Minimal record (only required fields)
# ---------------------------------------------------------------------------


class TestFromIngestRecordMinimal:
    def test_minimal_envelope_parses_without_error(self):
        minimal = {
            "identity": {
                "project_id": "p1",
                "uap_id": "u1",
            }
        }
        rec = UAPRecord.from_ingest_record(minimal)
        assert rec.ingest.project_id == "p1"
        assert rec.event_id == "u1"
        assert rec.content.doc_type == "post"
        assert rec.context.keywords_matched == []
        assert rec.content.attachments == []
        assert rec.signals.engagement.like_count == 0
