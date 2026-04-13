"""E2E tests: format detection.

Tests that analysis-srv correctly identifies and processes the two supported
ingest wire formats, and rejects unknown formats without emitting Kafka output.

Covered scenarios:
  1. ingest-srv flat format (has `identity` block) → output published
  2. legacy UAP format     (has `uap_version`)      → output published
  3. unknown format        (neither `identity` nor `uap_version`) → no output, error

Each test runs against a real Kafka broker (testcontainers or KAFKA_BOOTSTRAP_SERVERS).
"""

import json

import pytest

from tests.e2e.helpers import (
    E2ETestHarness,
    make_ingest_envelope,
    make_legacy_uap_envelope,
    TOPIC_BATCH,
    TOPIC_DIGEST,
)


@pytest.mark.e2e
async def test_ingest_srv_flat_format_produces_output(harness: E2ETestHarness):
    """ingest-srv flat format (identity block) → batch.completed + report.digest published.

    This is the primary production path. The envelope has:
    - identity.project_id
    - identity.uap_id
    - content.text
    - engagement fields

    Expected:
    - result.batch has exactly 1 message
    - result.digest has exactly 1 message
    - No pipeline error
    """
    envelope = make_ingest_envelope(
        project_id="proj-format-test-001",
        domain_type_code="vinfast",
        text="Xe VinFast VF8 rất tiết kiệm điện, đi được xa.",
    )

    result = await harness.run(envelope)

    assert result.error is None, f"Expected no error, got: {result.error}"
    assert result.published, "Expected at least one Kafka message to be published"
    assert len(result.batch) == 1, (
        f"Expected exactly 1 message on {TOPIC_BATCH}, got {len(result.batch)}"
    )
    assert len(result.digest) == 1, (
        f"Expected exactly 1 message on {TOPIC_DIGEST}, got {len(result.digest)}"
    )


@pytest.mark.e2e
async def test_legacy_uap_format_still_produces_output(harness: E2ETestHarness):
    """Legacy UAP format (uap_version='1.0') → output still published.

    The legacy format uses nested ingest/content/signals blocks and
    a top-level uap_version field. analysis-srv must continue supporting
    this format for backwards compatibility with older ingest pipelines.

    Expected:
    - result.batch has exactly 1 message
    - result.digest has exactly 1 message
    - No pipeline error
    """
    envelope = make_legacy_uap_envelope(
        project_id="proj-legacy-format-001",
    )

    result = await harness.run_legacy(envelope)

    assert result.error is None, f"Expected no error, got: {result.error}"
    assert result.published, "Expected at least one Kafka message to be published"
    assert len(result.batch) == 1, (
        f"Expected exactly 1 message on {TOPIC_BATCH}, got {len(result.batch)}"
    )
    assert len(result.digest) == 1, (
        f"Expected exactly 1 message on {TOPIC_DIGEST}, got {len(result.digest)}"
    )


@pytest.mark.e2e
async def test_unknown_format_produces_no_output(harness: E2ETestHarness):
    """Unknown format (no `identity`, no `uap_version`) → pipeline error, no Kafka output.

    An envelope that looks like a completely different schema should be rejected
    by the parser. No Kafka messages should be emitted, and the error field
    must be set on the result to indicate a validation failure.

    This verifies the parser's fail-fast behaviour rather than silently
    publishing garbage to downstream consumers.

    Expected:
    - result.error is set (ErrUAPValidation or similar)
    - result.published == False (no Kafka output)
    """
    unknown_envelope = {
        "message_type": "web_scraper_legacy",
        "source": "scrapy_pipeline_v2",
        "payload": {
            "url": "https://example.com/post/123",
            "text": "Some scraped text content",
            "scraped_at": "2024-03-01T08:00:00Z",
        },
    }

    result = await harness.run(unknown_envelope)

    assert result.error is not None, (
        "Expected a validation error for unknown format, but error is None"
    )
    assert not result.published, (
        f"Expected no Kafka output for unknown format, "
        f"but got: batch={result.batch}, digest={result.digest}"
    )
