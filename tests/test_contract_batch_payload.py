from internal.contract_publisher.type import RunContext
from internal.contract_publisher.usecase.publish_batch import build_batch_completed_payload
from internal.model.insight_message import InsightMessage, Identity, Content, NLP, NLPEntity
from internal.model.uap import (
    UAPAuthor,
    UAPContent,
    UAPContext,
    UAPEntity,
    UAPIngest,
    UAPRecord,
    UAPSignals,
    UAPSource,
)


def _make_uap() -> UAPRecord:
    return UAPRecord(
        event_id="event-1",
        ingest=UAPIngest(
            project_id="proj-1",
            source=UAPSource(source_id="src-1", source_type="facebook"),
            entity=UAPEntity(entity_type="brand", entity_name="VinFast", brand="VinFast"),
        ),
        content=UAPContent(
            doc_id="doc-1",
            doc_type="post",
            text="VinFast post",
            published_at="2026-04-23T00:00:00Z",
            author=UAPAuthor(author_id="author-1", display_name="Author One"),
        ),
        context=UAPContext(campaign_id="camp-1"),
        signals=UAPSignals(),
    )


def test_batch_payload_includes_nlp_entities_from_insight_message():
    uap = _make_uap()
    msg = InsightMessage(
        identity=Identity(
            source_type="facebook",
            source_id="src-1",
            doc_id="doc-1",
            doc_type="post",
            published_at="2026-04-23T00:00:00Z",
        ),
        content=Content(text="VinFast post", clean_text="VinFast post"),
        nlp=NLP(
            entities=[
                NLPEntity(type="BRAND", value="VinFast", confidence=0.9),
            ]
        ),
    )
    ctx = RunContext(
        run_id="run-1",
        project_id="proj-1",
        campaign_id="camp-1",
        platform="facebook",
        domain_overlay="vinfast",
        analysis_window_start="2026-04-23T00:00:00Z",
        analysis_window_end="2026-04-23T00:05:00Z",
    )

    payload = build_batch_completed_payload([(uap, msg)], ctx)
    entities = payload["documents"][0]["nlp"]["entities"]

    assert entities == [{"type": "BRAND", "value": "VinFast"}]
