# Implement Plan Index

Muc tieu: bo tai lieu implement chi tiet de chuyen core + business requirements tu smap-analyse vao analysis-srv theo clean architecture Python.

## Cac phase

1. `phase_0_readiness.md` - Chuan bi, dong bo pham vi, freeze contracts.
2. `phase_1_foundation_and_skeleton.md` - Dung khung module va wiring.
3. `phase_2_ingestion_and_normalization.md` - Ingestion UAP + normalize.
4. `phase_3_quality_dedup_spam_threads.md` - Dedup, spam, thread context.
5. `phase_4_enrichment_entity_semantic_topic.md` - Enrichment core.
6. `phase_5_reporting_and_insights.md` - Marts, metrics, BI, insights.
7. `phase_6_contract_publish_and_crisis.md` - Contract knowledge + crisis project.
8. `phase_7_observability_reliability.md` - Trace, outbox, retry, DLQ, perf.
9. `phase_8_cutover_and_handover.md` - Shadow run, canary, cutover, rollback.
10. `phase_gate_checklist.md` - Checklist gate chung cho moi phase.

## Cach su dung

- Team lead chot owner va ETA cho tung phase.
- Moi phase can co design review + code review + test report.
- Chi duoc move phase tiep theo khi pass gate checklist.
