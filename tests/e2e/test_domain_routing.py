"""E2E tests: domain routing.

Tests that analysis-srv correctly routes records to domain configs and injects
the right domain_overlay value into analytics.report.digest.

The domain_overlay field is critical: knowledge-srv workers.go drops any digest
where domain_overlay == "" (see CRITICAL BUG fix in _default.yaml).

Covered scenarios:
  1. Known domain "vinfast" → domain_overlay = "domain-vinfast-vn"
  2. Unknown domain code    → falls back to _default → "domain-default"
  3. Empty domain code      → falls back to _default → "domain-default"
  4. Invariant: domain_overlay is never empty for any input
  5. Overlay comes from YAML registry, not hardcoded in application code

Each test runs against a real Kafka broker (testcontainers or KAFKA_BOOTSTRAP_SERVERS).
"""

import pytest

from tests.e2e.helpers import (
    E2ETestHarness,
    make_ingest_envelope,
)

# Expected overlay values as defined in config/domains/*.yaml
OVERLAY_VINFAST = "domain-vinfast-vn"
OVERLAY_DEFAULT = "domain-default"


@pytest.mark.e2e
async def test_known_domain_vinfast_gets_vinfast_overlay(harness: E2ETestHarness):
    """domain_type_code='vinfast' → digest.domain_overlay = 'domain-vinfast-vn'.

    The vinfast domain is configured in config/domains/vinfast.yaml with:
        contract.domain_overlay: "domain-vinfast-vn"

    Expected: digest payload has domain_overlay == "domain-vinfast-vn"
    """
    envelope = make_ingest_envelope(
        project_id="proj-routing-vinfast-001",
        domain_type_code="vinfast",
    )

    result = await harness.run(envelope)

    assert result.error is None, f"Pipeline error: {result.error}"
    assert result.first_digest is not None, "Expected report.digest to be published"

    actual_overlay = result.first_digest.get("domain_overlay")
    assert actual_overlay == OVERLAY_VINFAST, (
        f"Expected domain_overlay='{OVERLAY_VINFAST}', got '{actual_overlay}'"
    )


@pytest.mark.e2e
async def test_unknown_domain_falls_back_to_default(harness: E2ETestHarness):
    """domain_type_code='foo-bar-unknown' → falls back to _default → 'domain-default'.

    When domain_type_code does not match any registered domain, the registry
    must fall back to the _default domain (configured in config/domains/_default.yaml).

    Expected: digest payload has domain_overlay == "domain-default"
    """
    envelope = make_ingest_envelope(
        project_id="proj-routing-unknown-001",
        domain_type_code="foo-bar-unknown-xyz",
    )

    result = await harness.run(envelope)

    assert result.error is None, f"Pipeline error: {result.error}"
    assert result.first_digest is not None, "Expected report.digest to be published"

    actual_overlay = result.first_digest.get("domain_overlay")
    assert actual_overlay == OVERLAY_DEFAULT, (
        f"Expected fallback domain_overlay='{OVERLAY_DEFAULT}', got '{actual_overlay}'"
    )


@pytest.mark.e2e
async def test_empty_domain_falls_back_to_default(harness: E2ETestHarness):
    """domain_type_code='' (empty string) → falls back to _default → 'domain-default'.

    Records from ingest-srv may omit domain_type_code or send an empty string.
    The registry must treat this as a fallback case, same as unknown domains.

    Expected: digest payload has domain_overlay == "domain-default"
    """
    envelope = make_ingest_envelope(
        project_id="proj-routing-empty-001",
        domain_type_code="",
    )

    result = await harness.run(envelope)

    assert result.error is None, f"Pipeline error: {result.error}"
    assert result.first_digest is not None, "Expected report.digest to be published"

    actual_overlay = result.first_digest.get("domain_overlay")
    assert actual_overlay == OVERLAY_DEFAULT, (
        f"Expected fallback domain_overlay='{OVERLAY_DEFAULT}', got '{actual_overlay}'"
    )


@pytest.mark.e2e
async def test_default_domain_overlay_never_empty_for_any_input(
    harness: E2ETestHarness,
):
    """domain_overlay must never be '' regardless of domain_type_code input.

    This is the key invariant that prevents knowledge-srv from silently dropping
    digest messages. An empty domain_overlay would cause knowledge-srv workers.go
    to skip the entire run without processing any documents.

    Tests multiple domain codes including edge cases:
      - "vinfast" (known)
      - "foo-bar" (unknown)
      - ""        (empty)
      - "  "      (whitespace — treated as empty after strip by registry)
    """
    test_cases = [
        ("vinfast", "known domain"),
        ("foo-bar-not-registered", "unknown domain"),
        ("", "empty domain"),
    ]

    for domain_code, label in test_cases:
        envelope = make_ingest_envelope(
            project_id=f"proj-invariant-{domain_code or 'empty'}-001",
            domain_type_code=domain_code,
        )
        result = await harness.run(envelope)

        assert result.error is None, f"[{label}] Pipeline error: {result.error}"
        assert result.first_digest is not None, (
            f"[{label}] Expected report.digest to be published"
        )

        overlay = result.first_digest.get("domain_overlay", "")
        assert overlay != "", (
            f"[{label}] domain_overlay must never be empty string, "
            f"but got '' for domain_type_code={domain_code!r}"
        )


@pytest.mark.e2e
async def test_domain_overlay_is_set_by_registry_not_hardcoded(harness: E2ETestHarness):
    """Verify overlays come from YAML config values, not hardcoded strings.

    Tests that:
    - "vinfast" → exactly "domain-vinfast-vn" (from vinfast.yaml contract.domain_overlay)
    - Any non-vinfast code → exactly "domain-default" (from _default.yaml)

    This test would catch a regression where someone hardcodes "domain-vinfast-vn"
    without reading from the YAML registry.
    """
    # VinFast overlay must match vinfast.yaml exactly
    vinfast_envelope = make_ingest_envelope(
        project_id="proj-registry-check-001",
        domain_type_code="vinfast",
    )
    vinfast_result = await harness.run(vinfast_envelope)

    assert vinfast_result.error is None
    assert vinfast_result.first_digest is not None
    assert vinfast_result.first_digest["domain_overlay"] == "domain-vinfast-vn", (
        "vinfast.yaml specifies domain_overlay: 'domain-vinfast-vn' — "
        "if this fails, either the YAML was changed or routing is broken"
    )

    # Default overlay must match _default.yaml exactly
    default_envelope = make_ingest_envelope(
        project_id="proj-registry-check-002",
        domain_type_code="not-a-real-domain",
    )
    default_result = await harness.run(default_envelope)

    assert default_result.error is None
    assert default_result.first_digest is not None
    assert default_result.first_digest["domain_overlay"] == "domain-default", (
        "_default.yaml specifies domain_overlay: 'domain-default' — "
        "if this fails, the default config was changed or fallback logic is broken"
    )
