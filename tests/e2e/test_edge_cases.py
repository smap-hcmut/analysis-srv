"""E2E tests: edge cases and robustness.

Tests that analysis-srv handles abnormal inputs gracefully:
- Malformed JSON
- Empty byte payloads
- Missing required fields
- Unicode / long text
- Null / zero engagement
- Empty media list
- Missing content block
- Very long text (5000+ chars)
- domain_overlay invariant across all inputs

All edge cases must either:
  a) Return a clear error (no Kafka output) for invalid inputs, OR
  b) Publish valid output (no crash) for unusual-but-valid inputs

Each test runs against a real Kafka broker (testcontainers or KAFKA_BOOTSTRAP_SERVERS).
"""

import json

import pytest

from tests.e2e.helpers import (
    E2ETestHarness,
    make_ingest_envelope,
)


# ---------------------------------------------------------------------------
# Invalid input — should return error, no Kafka output
# ---------------------------------------------------------------------------


@pytest.mark.e2e
async def test_malformed_json_returns_error_no_kafka_output(harness: E2ETestHarness):
    """Malformed JSON bytes → JSONDecodeError, no Kafka messages published.

    Expected:
    - result.error == 'JSONDecodeError'
    - result.published == False
    """
    result = await harness.run_bytes(b"{ not valid json: [}")

    assert result.error == "JSONDecodeError", (
        f"Expected JSONDecodeError, got: {result.error}"
    )
    assert not result.published, (
        f"Expected no Kafka output for malformed JSON, "
        f"but got: batch={result.batch}, digest={result.digest}"
    )


@pytest.mark.e2e
async def test_empty_bytes_returns_error(harness: E2ETestHarness):
    """Empty byte payload → JSONDecodeError, no Kafka messages published.

    An empty payload might arrive from a misconfigured producer or a
    Kafka message with a null value.

    Expected:
    - result.error is set
    - result.published == False
    """
    result = await harness.run_bytes(b"")

    assert result.error is not None, (
        "Expected an error for empty bytes, but result.error is None"
    )
    assert not result.published, "Expected no Kafka output for empty bytes"


@pytest.mark.e2e
async def test_missing_project_id_raises_validation_error(harness: E2ETestHarness):
    """Envelope without identity.project_id → ErrUAPValidation, no Kafka output.

    identity.project_id is a required field. Without it, analysis-srv cannot
    associate the record with a project, so the entire record must be rejected.

    Expected:
    - result.error == 'ErrUAPValidation'
    - result.published == False
    """
    envelope = make_ingest_envelope(project_id="proj-edge-pid-001")
    # Remove project_id from identity
    envelope["identity"]["project_id"] = ""

    result = await harness.run(envelope)

    assert result.error == "ErrUAPValidation", (
        f"Expected ErrUAPValidation for missing project_id, got: {result.error}"
    )
    assert not result.published, "Expected no Kafka output when project_id is missing"


@pytest.mark.e2e
async def test_missing_uap_id_raises_validation_error(harness: E2ETestHarness):
    """Envelope without identity.uap_id → ErrUAPValidation, no Kafka output.

    identity.uap_id is the primary document identifier. Without it, analysis-srv
    cannot construct a valid document record.

    Expected:
    - result.error == 'ErrUAPValidation'
    - result.published == False
    """
    envelope = make_ingest_envelope(project_id="proj-edge-uid-001")
    # Remove uap_id from identity
    envelope["identity"]["uap_id"] = ""

    result = await harness.run(envelope)

    assert result.error == "ErrUAPValidation", (
        f"Expected ErrUAPValidation for missing uap_id, got: {result.error}"
    )
    assert not result.published, "Expected no Kafka output when uap_id is missing"


# ---------------------------------------------------------------------------
# Valid but unusual inputs — should publish without crash
# ---------------------------------------------------------------------------


@pytest.mark.e2e
async def test_vietnamese_unicode_text_preserved_in_batch(harness: E2ETestHarness):
    """Vietnamese text with diacritics must be preserved intact in the batch document.

    Vietnamese uses combining diacritical marks (e.g. ề, ổ, ắ) that can be
    corrupted by incorrect encoding. The pipeline must preserve them end-to-end.

    Expected:
    - Batch document clean_text contains the original Vietnamese text.
    - No encoding corruption (no replacement characters, no ASCII fallback).
    """
    vietnamese_text = (
        "Xe VinFast VF8 chạy êm ái, pin bền, phù hợp gia đình Việt Nam. "
        "Tôi rất hài lòng với dịch vụ hậu mãi xuất sắc của hãng!"
    )
    envelope = make_ingest_envelope(
        project_id="proj-edge-unicode-001",
        text=vietnamese_text,
    )

    result = await harness.run(envelope)

    assert result.error is None, f"Pipeline error: {result.error}"
    assert result.first_batch is not None

    documents = result.first_batch.get("documents", [])
    assert documents, "Expected at least one document"

    clean_text = documents[0].get("content", {}).get("clean_text", "")
    assert clean_text == vietnamese_text, (
        f"Vietnamese text was corrupted in the pipeline.\n"
        f"Expected: {vietnamese_text!r}\n"
        f"Got:      {clean_text!r}"
    )


@pytest.mark.e2e
async def test_null_engagement_fields_default_to_zero(harness: E2ETestHarness):
    """Null/missing engagement block → all engagement counts default to 0.

    Some ingest records may lack engagement data (e.g. news articles, uploads).
    The pipeline must not crash and must produce a valid batch document with
    zero engagement counts.

    Expected:
    - No pipeline error
    - Batch document engagement is {"likes": 0, "comments": 0, "shares": 0, "views": 0}
    """
    envelope = make_ingest_envelope(project_id="proj-edge-eng-001")
    # Replace the engagement block with null
    envelope["engagement"] = None

    result = await harness.run(envelope)

    assert result.error is None, f"Pipeline error: {result.error}"
    assert result.first_batch is not None

    documents = result.first_batch.get("documents", [])
    assert documents, "Expected at least one document"

    engagement = (
        documents[0].get("business", {}).get("impact", {}).get("engagement", {})
    )
    assert engagement.get("likes") == 0, (
        f"Expected likes=0, got {engagement.get('likes')}"
    )
    assert engagement.get("comments") == 0, (
        f"Expected comments=0, got {engagement.get('comments')}"
    )
    assert engagement.get("shares") == 0, (
        f"Expected shares=0, got {engagement.get('shares')}"
    )
    assert engagement.get("views") == 0, (
        f"Expected views=0, got {engagement.get('views')}"
    )


@pytest.mark.e2e
async def test_null_media_list_produces_no_crash(harness: E2ETestHarness):
    """Null or empty media list → no crash, batch published normally.

    Media is optional in the ingest envelope. When media is null or [], the
    pipeline must process the record normally (no attachments, just text).

    Expected:
    - No pipeline error for media=None
    - No pipeline error for media=[]
    - Batch published for both cases
    """
    # media=None
    envelope_null = make_ingest_envelope(
        project_id="proj-edge-media-001",
        media=None,
    )
    result_null = await harness.run(envelope_null)
    assert result_null.error is None, (
        f"Pipeline error for media=None: {result_null.error}"
    )
    assert result_null.published, "Expected output for media=None"

    # media=[]
    envelope_empty = make_ingest_envelope(
        project_id="proj-edge-media-002",
        media=[],
    )
    result_empty = await harness.run(envelope_empty)
    assert result_empty.error is None, (
        f"Pipeline error for media=[]: {result_empty.error}"
    )
    assert result_empty.published, "Expected output for media=[]"


@pytest.mark.e2e
async def test_missing_content_block_no_crash(harness: E2ETestHarness):
    """Empty content block (text='') → no crash, batch published with stub text.

    Records without meaningful text are unusual but valid. The stub NLP
    factory falls back to 'stub text' when content.text is empty.

    Expected:
    - No pipeline error
    - Batch is published (stub text satisfies the document gate)
    """
    envelope = make_ingest_envelope(
        project_id="proj-edge-content-001",
        text="",  # empty text
    )

    result = await harness.run(envelope)

    assert result.error is None, f"Pipeline error: {result.error}"
    assert result.published, (
        "Expected output even with empty text (stub NLP provides fallback text)"
    )


@pytest.mark.e2e
async def test_very_long_text_5000_chars(harness: E2ETestHarness):
    """Text with 5000 characters → pipeline handles without crash or truncation error.

    Long-form content (news articles, detailed reviews) may be very long.
    The pipeline must process these without crashing or hitting memory limits.

    Expected:
    - No pipeline error
    - Batch published with the full text preserved in clean_text
    - Summary is truncated to SUMMARY_MAX_CHARS (120 chars)
    """
    long_text = "Đây là bài đánh giá chi tiết về xe VinFast. " * 115  # ~5060 chars
    assert len(long_text) >= 5000

    envelope = make_ingest_envelope(
        project_id="proj-edge-longtext-001",
        text=long_text,
    )

    result = await harness.run(envelope)

    assert result.error is None, f"Pipeline error: {result.error}"
    assert result.first_batch is not None

    documents = result.first_batch.get("documents", [])
    assert documents, "Expected at least one document"
    doc = documents[0]

    # Full text must be preserved in clean_text
    clean_text = doc.get("content", {}).get("clean_text", "")
    assert len(clean_text) >= 5000, (
        f"Expected clean_text to preserve full {len(long_text)}-char text, "
        f"got {len(clean_text)} chars"
    )

    # Summary must be truncated (SUMMARY_MAX_CHARS = 120)
    summary = doc.get("content", {}).get("summary", "")
    assert len(summary) <= 120, (
        f"Expected summary to be truncated to ≤120 chars, got {len(summary)} chars"
    )


@pytest.mark.e2e
async def test_knowledge_srv_gate_domain_overlay_never_empty_invariant(
    harness: E2ETestHarness,
):
    """Invariant: domain_overlay is never empty across ALL tested domain codes.

    This is an explicit regression test for the CRITICAL BUG where _default.yaml
    had `domain_overlay: ""`, causing knowledge-srv to silently drop every digest
    for records without an explicit domain config.

    Tests a broad range of inputs including extreme edge cases:
    - Registered domain ("vinfast")
    - Completely random/unknown domain
    - Empty string
    - Domain code with special characters
    - Domain code that looks like a registered domain but isn't exact

    Expected: For every input, digest.domain_overlay != ""
    """
    test_inputs = [
        "vinfast",
        "unknown-brand-xyz",
        "",
        "UPPERCASE_DOMAIN",
        "domain-with-hyphens",
        "123numeric",
        "vinfast_typo",  # Similar to registered but not exact
    ]

    for domain_code in test_inputs:
        envelope = make_ingest_envelope(
            project_id=f"proj-invariant-gate-001",
            domain_type_code=domain_code,
        )
        result = await harness.run(envelope)

        assert result.error is None, (
            f"Unexpected error for domain_code={domain_code!r}: {result.error}"
        )
        assert result.first_digest is not None, (
            f"No digest for domain_code={domain_code!r}"
        )

        overlay = result.first_digest.get("domain_overlay", "")
        assert overlay != "", (
            f"CRITICAL REGRESSION: domain_overlay is empty for domain_code={domain_code!r}. "
            f"knowledge-srv will DROP this digest. "
            f"Check config/domains/_default.yaml contract.domain_overlay != ''"
        )
