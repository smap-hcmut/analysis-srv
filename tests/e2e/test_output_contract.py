"""E2E tests: output contract validation.

Tests that the messages published to analytics.batch.completed and
analytics.report.digest conform to the contract schema expected by knowledge-srv.

Contract reference: contract.md v1.2

Topics under test:
  - analytics.batch.completed  (Layer 3) — full documents[] array
  - analytics.report.digest    (Layer 1) — run summary, triggers export

analytics.insights.published (Layer 2) is not tested here because it requires
InsightCards from Phase 4+ (currently empty in stub mode).

Covered scenarios:
   1. batch.completed published to correct Kafka topic
   2. batch payload has project_id field
   3. batch payload has documents[] array
   4. batch document has all required sub-fields (identity, content, nlp, business, rag)
   5. report.digest published to correct Kafka topic
   6. digest payload has project_id field
   7. digest payload has non-empty domain_overlay  ← CRITICAL knowledge-srv gate
   8. batch.completed arrives BEFORE report.digest (publish ordering guarantee)
   9. engagement counts are propagated from ingest envelope to batch document
  10. rag field in batch document reflects should_index argument

Each test runs against a real Kafka broker (testcontainers or KAFKA_BOOTSTRAP_SERVERS).
"""

import pytest

from tests.e2e.helpers import (
    E2ETestHarness,
    make_ingest_envelope,
    TOPIC_BATCH,
    TOPIC_DIGEST,
)


@pytest.mark.e2e
async def test_batch_completed_published_to_correct_topic(harness: E2ETestHarness):
    """analytics.batch.completed receives exactly one message per run.

    Expected: result.batch has 1 message, result.error is None.
    """
    result = await harness.run(make_ingest_envelope(project_id="proj-contract-001"))

    assert result.error is None
    assert len(result.batch) == 1, (
        f"Expected exactly 1 message on {TOPIC_BATCH}, got {len(result.batch)}"
    )


@pytest.mark.e2e
async def test_batch_payload_has_project_id(harness: E2ETestHarness):
    """batch.completed payload must include a non-empty project_id.

    project_id is required by knowledge-srv to associate documents with a project.
    An empty project_id causes the batch gate to drop the entire message.

    Expected: payload['project_id'] == the project_id from the ingest envelope.
    """
    project_id = "proj-contract-batch-pid-001"
    result = await harness.run(make_ingest_envelope(project_id=project_id))

    assert result.error is None
    assert result.first_batch is not None

    payload_pid = result.first_batch.get("project_id")
    assert payload_pid == project_id, (
        f"Expected project_id='{project_id}' in batch, got '{payload_pid}'"
    )


@pytest.mark.e2e
async def test_batch_payload_has_documents_array(harness: E2ETestHarness):
    """batch.completed payload must include a 'documents' array.

    The documents[] array is the primary data carrier for knowledge-srv ingestion.
    It must be present and non-empty for a valid ingest envelope.

    Expected: payload['documents'] is a non-empty list.
    """
    result = await harness.run(
        make_ingest_envelope(project_id="proj-contract-docs-001")
    )

    assert result.error is None
    assert result.first_batch is not None

    documents = result.first_batch.get("documents")
    assert isinstance(documents, list), (
        f"Expected 'documents' to be a list, got {type(documents)}"
    )
    assert len(documents) == 1, (
        f"Expected exactly 1 document in batch (one ingest record), got {len(documents)}"
    )


@pytest.mark.e2e
async def test_batch_document_has_required_fields(harness: E2ETestHarness):
    """Each document in batch.completed must have all required sub-fields.

    Contract Section 2 mandates these top-level keys per document:
      - identity   (uap_id, uap_type, platform, published_at, uap_media_type)
      - content    (clean_text, summary)
      - nlp        (sentiment with label/score, aspects[], entities[])
      - business   (impact with engagement, impact_score, priority)
      - rag        (boolean gate for RAG indexing)

    Expected: all required keys are present on the document dict.
    """
    result = await harness.run(
        make_ingest_envelope(project_id="proj-contract-fields-001")
    )

    assert result.error is None
    assert result.first_batch is not None

    documents = result.first_batch.get("documents", [])
    assert documents, "Expected at least one document"
    doc = documents[0]

    # Top-level required fields
    required_top_level = {"identity", "content", "nlp", "business", "rag"}
    missing = required_top_level - set(doc.keys())
    assert not missing, f"Document missing required top-level fields: {missing}"

    # identity sub-fields
    identity = doc.get("identity", {})
    required_identity = {
        "uap_id",
        "uap_type",
        "platform",
        "published_at",
        "uap_media_type",
    }
    missing_identity = required_identity - set(identity.keys())
    assert not missing_identity, f"Document identity missing fields: {missing_identity}"

    # content sub-fields
    content = doc.get("content", {})
    assert "clean_text" in content, "Document content missing 'clean_text'"
    assert "summary" in content, "Document content missing 'summary'"

    # nlp sub-fields
    nlp = doc.get("nlp", {})
    assert "sentiment" in nlp, "Document nlp missing 'sentiment'"
    sentiment = nlp.get("sentiment", {})
    assert "label" in sentiment, "Document nlp.sentiment missing 'label'"
    assert "score" in sentiment, "Document nlp.sentiment missing 'score'"
    assert "aspects" in nlp, "Document nlp missing 'aspects'"
    assert "entities" in nlp, "Document nlp missing 'entities'"

    # business sub-fields
    business = doc.get("business", {})
    assert "impact" in business, "Document business missing 'impact'"
    impact = business.get("impact", {})
    assert "engagement" in impact, "Document business.impact missing 'engagement'"
    assert "impact_score" in impact, "Document business.impact missing 'impact_score'"
    assert "priority" in impact, "Document business.impact missing 'priority'"

    # rag field is a boolean
    rag = doc.get("rag")
    assert isinstance(rag, bool), (
        f"Document 'rag' must be a boolean, got {type(rag)}: {rag}"
    )


@pytest.mark.e2e
async def test_digest_published_to_correct_topic(harness: E2ETestHarness):
    """analytics.report.digest receives exactly one message per run.

    Expected: result.digest has 1 message, result.error is None.
    """
    result = await harness.run(
        make_ingest_envelope(project_id="proj-contract-digest-001")
    )

    assert result.error is None
    assert len(result.digest) == 1, (
        f"Expected exactly 1 message on {TOPIC_DIGEST}, got {len(result.digest)}"
    )


@pytest.mark.e2e
async def test_digest_payload_has_project_id(harness: E2ETestHarness):
    """digest payload must include the project_id from the ingest record.

    knowledge-srv uses project_id in the digest to identify which project's
    pipeline triggered the run.

    Expected: digest['project_id'] == the project_id from the envelope.
    """
    project_id = "proj-contract-digest-pid-001"
    result = await harness.run(make_ingest_envelope(project_id=project_id))

    assert result.error is None
    assert result.first_digest is not None

    payload_pid = result.first_digest.get("project_id")
    assert payload_pid == project_id, (
        f"Expected project_id='{project_id}' in digest, got '{payload_pid}'"
    )


@pytest.mark.e2e
async def test_digest_payload_domain_overlay_non_empty(harness: E2ETestHarness):
    """digest.domain_overlay must NEVER be empty string.

    CRITICAL: This is the gate condition in knowledge-srv workers.go.
    An empty domain_overlay causes knowledge-srv to silently drop the digest,
    which means no export is triggered and no reports are generated.

    This test was added after the CRITICAL BUG where _default.yaml had
    `domain_overlay: ""`, causing all fallback-routed records to be dropped
    by knowledge-srv.

    Expected: digest['domain_overlay'] is a non-empty string.
    """
    result = await harness.run(
        make_ingest_envelope(
            project_id="proj-contract-overlay-001",
            domain_type_code="vinfast",
        )
    )

    assert result.error is None
    assert result.first_digest is not None

    overlay = result.first_digest.get("domain_overlay", "")
    assert overlay != "", (
        "CRITICAL: domain_overlay is empty string in digest — "
        "knowledge-srv will drop this digest and no reports will be generated. "
        "Check config/domains/_default.yaml has domain_overlay: 'domain-default'"
    )
    assert isinstance(overlay, str), (
        f"domain_overlay must be a string, got {type(overlay)}"
    )


@pytest.mark.e2e
async def test_batch_arrives_before_digest(harness: E2ETestHarness):
    """analytics.batch.completed must arrive BEFORE analytics.report.digest.

    Contract mandate (publish_order.py): batch → insights → digest.
    knowledge-srv uses the digest as a "run complete" signal. If digest
    arrives before batch, the export would be triggered before documents
    are available, resulting in empty exports.

    Expected:
    - All batch topic messages appear before any digest topic messages
      in the inter-topic arrival order.
    """
    result = await harness.run(
        make_ingest_envelope(project_id="proj-contract-order-001")
    )

    assert result.error is None
    assert result.batch, "Expected batch.completed message"
    assert result.digest, "Expected report.digest message"
    assert result.arrival_order, "Expected ordered message list from consumer"

    # Extract topic positions in arrival order
    topics_in_order = [topic for topic, _ in result.arrival_order]
    batch_positions = [i for i, t in enumerate(topics_in_order) if t == TOPIC_BATCH]
    digest_positions = [i for i, t in enumerate(topics_in_order) if t == TOPIC_DIGEST]

    assert batch_positions, f"No {TOPIC_BATCH} messages found in arrival_order"
    assert digest_positions, f"No {TOPIC_DIGEST} messages found in arrival_order"

    # Every batch message must arrive before every digest message
    assert max(batch_positions) < min(digest_positions), (
        f"ORDERING VIOLATION: batch positions {batch_positions} vs "
        f"digest positions {digest_positions} — batch must come before digest. "
        f"Full order: {topics_in_order}"
    )


@pytest.mark.e2e
async def test_engagement_counts_propagated_to_batch(harness: E2ETestHarness):
    """Engagement counts from ingest envelope must appear in batch document.

    The ingest envelope carries social engagement signals (likes, comments,
    shares, views). These must be propagated through the pipeline and appear
    in the batch document's business.impact.engagement object.

    Expected: engagement values in batch doc match the envelope values.
    """
    envelope = make_ingest_envelope(
        project_id="proj-contract-engagement-001",
        likes=1234,
        comments_count=56,
        shares=78,
        views=99000,
    )

    result = await harness.run(envelope)

    assert result.error is None
    assert result.first_batch is not None

    documents = result.first_batch.get("documents", [])
    assert documents, "Expected at least one document"
    doc = documents[0]

    engagement = doc.get("business", {}).get("impact", {}).get("engagement", {})

    assert engagement.get("likes") == 1234, (
        f"Expected likes=1234, got {engagement.get('likes')}"
    )
    assert engagement.get("comments") == 56, (
        f"Expected comments=56, got {engagement.get('comments')}"
    )
    assert engagement.get("shares") == 78, (
        f"Expected shares=78, got {engagement.get('shares')}"
    )
    assert engagement.get("views") == 99000, (
        f"Expected views=99000, got {engagement.get('views')}"
    )


@pytest.mark.e2e
async def test_rag_field_reflects_should_index(harness: E2ETestHarness):
    """The 'rag' boolean field in batch document reflects the should_index argument.

    knowledge-srv uses the rag field to decide whether to send a document
    to the RAG vector store. It must faithfully reflect the pipeline's decision.

    Expected:
    - should_index=True  → doc['rag'] == True
    - should_index=False → doc['rag'] == False
    """
    envelope = make_ingest_envelope(project_id="proj-contract-rag-001")

    # should_index=True
    result_true = await harness.run(envelope, should_index=True)
    assert result_true.error is None
    docs_true = (
        result_true.first_batch.get("documents", []) if result_true.first_batch else []
    )
    assert docs_true, "Expected documents in batch (should_index=True)"
    assert docs_true[0].get("rag") is True, (
        f"Expected rag=True for should_index=True, got {docs_true[0].get('rag')}"
    )

    # should_index=False
    result_false = await harness.run(envelope, should_index=False)
    assert result_false.error is None
    docs_false = (
        result_false.first_batch.get("documents", [])
        if result_false.first_batch
        else []
    )
    assert docs_false, "Expected documents in batch (should_index=False)"
    assert docs_false[0].get("rag") is False, (
        f"Expected rag=False for should_index=False, got {docs_false[0].get('rag')}"
    )
