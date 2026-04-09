"""usecase.py — ReportingUseCase: full Phase 5 reporting orchestration."""

from __future__ import annotations

from loguru import logger

from internal.reporting.interface import IReportingUseCase
from internal.reporting.type import (
    OntologyRegistryStub,
    ReportingInput,
    ReportingOutput,
)
from internal.reporting.usecase.build_marts import build_mart_bundle
from internal.reporting.usecase.build_bi_reports import build_report_bundle
from internal.reporting.usecase.build_layer1_payload import build_layer1_payload
from internal.reporting.usecase.build_layer2_payload import build_layer2_payloads


class ReportingUseCase(IReportingUseCase):
    """Assembles MartBundle, builds BI reports, and produces Layer 1 & 2 payloads."""

    def report(self, inp: ReportingInput) -> ReportingOutput:
        ontology = inp.ontology or OntologyRegistryStub()

        logger.debug(
            "reporting: building mart bundle",
            run_id=inp.run_id,
            mentions=len(inp.mentions),
        )
        mart = build_mart_bundle(
            mentions=inp.mentions,
            threads=inp.thread_bundle,
            enrichment=inp.enrichment_bundle,
            ontology=ontology,
            dedup_clusters=inp.dedup_clusters or [],
            author_quality=inp.author_quality or [],
        )

        logger.debug("reporting: building BI report bundle", run_id=inp.run_id)
        bi_reports = build_report_bundle(mart)

        logger.debug("reporting: building layer payloads", run_id=inp.run_id)
        layer1 = build_layer1_payload(
            run_id=inp.run_id,
            project_id=inp.project_id,
            campaign_id=inp.campaign_id,
            reports=bi_reports,
        )
        layer2 = build_layer2_payloads(
            run_id=inp.run_id,
            project_id=inp.project_id,
            campaign_id=inp.campaign_id,
            reports=bi_reports,
        )

        logger.info(
            "reporting: done",
            run_id=inp.run_id,
            insight_cards=len(bi_reports.insight_card_bundle.cards),
            layer2_messages=len(layer2),
        )

        return ReportingOutput(
            mart_bundle=mart,
            bi_reports=bi_reports,
            layer1_payload=layer1,
            layer2_payloads=layer2,
        )


__all__ = ["ReportingUseCase"]
