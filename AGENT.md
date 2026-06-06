# analysis-srv — Agent Reference

Read `/Users/ts.1126/Workspaces/smap/AGENT.md` first for cross-repo context. This file covers `analysis-srv` internals deep enough for any task: HTTP bug, consumer bug, NLP enrichment change, ontology update, crisis tuning, migration.

Owner of canonical analytics state for SMAP. Consumes UAP from Kafka, runs 9-phase pipeline, persists insights, publishes contract topics, exposes dashboard read API.

---

## 1. Process Topology

Two K8s deployments out of the same repo:

| Deployment | Entrypoint | Role |
| --- | --- | --- |
| `analysis-consumer` | `apps/consumer/main.py` | Long-running async Kafka consumer + pipeline executor |
| `analysis-api` | `apps/api/main.py` | Stateless FastAPI dashboard query service |

**Consumer startup wiring** (`apps/consumer/main.py`):
1. `load_config()` — YAML + env override (env wins; `.env` middle; `config/config.yaml` defaults).
2. Logger init at L74; aiokafka log level lowered; `ANALYTICS_OMP_NUM_THREADS` applied to BLAS/ONNX (L94–98).
3. PostgreSQL async pool with backoff retry `5s,10s,20s,30s,60s` (L109–120).
4. Redis with same backoff (L134–146).
5. NLP models: PhoBERT ONNX at `internal/model/phobert` (L174–182, 256 max tokens). SpaCy `xx_ent_wiki_sm` + YAKE `vi`, max 30 keywords (L185–197).
6. Kafka producer: idempotent, gzip, `acks=all`, `linger_ms=100` (L200–210).
7. Kafka consumer: group `analytics-service`, `max_poll_records=6` (env override), `max_poll_interval_ms=600000` (L218–230). Long poll because ONNX batch is slow.
8. `ConsumerRegistry.initialize()` (L69–70) builds pipeline services + DomainRegistry from `config/domains/`.
9. `ConsumerServer.start()` writes `/tmp/healthy` (server.py L134) — that file IS the K8s startup probe.
10. SIGTERM/SIGINT → `server.shutdown()` removes `/tmp/healthy` (L467).

**API startup**: FastAPI lifespan at `apps/api/main.py` L186, deps in `init_api_dependencies()` L86.

---

## 2. Nine-Phase Pipeline

Entrypoint: `ConsumerServer._handle_messages_batch()` (server.py L222) groups by `(project_id, domain_type_code)` then runs `run_pipeline()` (`internal/pipeline/usecase/run_pipeline.py`).

| Stage | Module | In → Out | Key tuning |
| --- | --- | --- | --- |
| 1 Normalization | `internal/normalization` | UAP → `MentionRecord` | language detect, quality flags. Always on. |
| 2 Dedup | `internal/dedup` | MentionRecord text | MinHash 64 perms, 16 bands, threshold `0.82` (constant.py) |
| 3 Spam | `internal/spam` | MentionRecord author | inorganic author score → `quality_weight`, `is_spam` |
| 4 Threads | `internal/threads` | MentionRecord | ThreadBundle root/parent/child + reply depth |
| 5 NLP enrichment | `internal/analytics/usecase/batch_enricher.py` | Records batch → `NLPFact[]` | 3-phase: per-record preprocess+intent+keywords → batch ONNX sentiment → per-record impact+builder |
| 6 Enrichment | `internal/enrichment` | NLP facts → `EnrichmentBundle` | NER + semantic topics, currently stub (flag off) |
| 7 Review | `internal/review` | Low-confidence facts → `ReviewQueue` | confidence cutoff; flag off |
| 8 Reporting | `internal/reporting` | Pipeline output → `BIReportBundle` (SOV/Buzz/Emerging/Issues) | Polars; flag off |
| 9 Crisis | `internal/crisis` | BI reports → `CrisisAssessment`, `CrisisLevel` | rule-based composite score |

**Feature flags** (`PipelineConfig` type.py L99–116). Default state:
```
enable_normalization=True   # always on
enable_dedup=False
enable_spam=False
enable_threads=False
enable_nlp=True             # MUST be explicitly true in config.yaml
enable_enrichment=False
enable_review=False
enable_reporting=False
enable_crisis=False
```
Missing pipeline services degrade gracefully (`batch_enricher.py` L136–170).

**Batch ONNX trick** (`batch_enricher.py` L89): phase 1 (L107–123) per-record preprocess + intent + keywords; phase 2 (L125–170) accumulates non-skipped records and calls `sentiment_analyzer.process_batch()` **once** for entire batch; phase 3 (L173–226) applies sentiment + impact + builds `NLPFact`.

---

## 3. NLP Enrichment

**PhoBERT ONNX** (`pkg/phobert_onnx/phobert_onnx.py`):
- Model path: `internal/model/phobert` (constant.py L13). Must exist before startup — no lazy download.
- 3-class labels: `POSITIVE | NEGATIVE | NEUTRAL`. Score `-1.0..+1.0`.
- Thresholds: `DEFAULT_THRESHOLD_POSITIVE=0.25`, `DEFAULT_THRESHOLD_NEGATIVE=-0.25`.
- Rating mapping: 1→-1.0, 2→-0.5, 3→0.0, 4→0.5, 5→+1.0.
- Tokenizer: PyVi, 256 max tokens. Per-aspect sentiment via keyword context window.
- Threading: default `ANALYTICS_OMP_NUM_THREADS=1` to avoid CPU oversubscription. Override with `ANALYTICS_ONNX_INTRA_OP_THREADS` / `ANALYTICS_ONNX_INTER_OP_THREADS`.

**Intent classification** (`internal/intent_classification`):
- Patterns in `config/intent_patterns.yaml` loaded at startup.
- Default confidence threshold `0.5`. Fallback intent: `DISCUSSION`.

**Keyword extraction**: YAKE statistical + SpaCy NER cascade. SpaCy `xx_ent_wiki_sm`, YAKE `vi`, `n=2`, `dedup_lim=0.8`, `max_keywords=30`. Entity weight `0.7`, chunk weight `0.5` (constants.py L41–42). Output: keyword + position + score + aspect + source tag.

**Fact types** (`internal/enrichment/type.py`):
- `EntityFact` (L65): mention_id, candidate_text, entity_type, confidence, resolution_kind (`canonical | concept | unresolved | alias_match`).
- `EntityCandidateClusterFact` (L98): unresolved cluster + normalized surface.
- `TopicFact`, `IssueSignalFact`, `SentimentFact` — Phase 4+ semantic.
- `SentimentLabel`: `positive | negative | neutral | mixed`.
- `IssueSeverity`: `low | medium | high | critical_like_proxy`.

---

## 4. Ontology System

**Two-layer config**:
- `config/ontology/*.yaml` — self-contained ontology per domain (entities, taxonomy, aspects, issues, intents, topics, channels). Example: `vinfast_vn.yaml` (15 entities, 18 aspects, 15 issues, 10 intents, 10 topics, 28 taxonomy nodes, 6 channels).
- `config/domains/*.yaml` — runtime pointer (`domain_code`, `ontology.path`, runtime `brand_names`/`topic_seeds`, contract overlay).

**Registry loading** (`internal/domain/loader.py`):
- `DomainLoader.load_from_dir("config/domains")` → immutable thread-safe `DomainRegistry`.
- Fallback to `_default` entry if domain not matched (L81–91).
- `DomainRuntimeConfig.load_ontology_registry()` (L54–63) returns `FileOntologyRegistry`.

**Adding a domain**:
1. Copy `config/ontology/vinfast_vn.yaml` → `<domain>_vn.yaml`. Self-contained.
2. Create `config/domains/<domain>.yaml` pointing to the ontology path; set runtime brand_names + topic_seeds.
3. Restart consumer pod. Registry is built once at startup — no hot reload.
4. EntityFact resolution needs canonical entity master data → put aliases in ontology.
5. Use overlay mechanism for tweaks; do NOT edit existing domain files in place.

---

## 5. Persistence

**Schema**: `schema_analysis` (constant.py L10). asyncpg + SQLAlchemy 2.x async. Pool size 20, max overflow 10. Statement timeout 25 000 ms default.

**Key tables**:
| Table | Purpose |
| --- | --- |
| `analysis.post_insight` | Main NLP result per mention. id (UUID), project_id, source_id, overall_sentiment, aspects JSONB, keywords[], engagement_score, business_relevance_score, created_at |
| `analysis.analytics_outbox` | Transactional outbox for Kafka (Phase 6 ready; not used yet) |
| `analysis.analytics_run_manifest` | Pipeline audit log: run_id, project_id, stage_timings, total_records |
| `analysis.latest_post_insight` (mat view) | DISTINCT ON (platform, source_id) ORDER BY updated_at DESC. Refreshed on-demand by `/ready` probe (api/main.py L149–174). |

**Migrations** (`migration/`):
- `001_create_analytics_outbox.sql`
- `002_create_analytics_run_manifest.sql`
- `004_optimize_post_insight_reads.sql` — indexes on `(project_id, business_relevance_score)`, `(project_id, engagement_score)`
- `005_relevant_post_insight_dedupe_index.sql` — relevance ≥ 0.45 dedup
- `006_posts_filter_dedupe_index.sql`
- `007_latest_post_insight_mart.sql` — materialized view with HARDCODED domain regex (logistics, HR/CRM) at L28–66; adding new domains requires SQL migration
- `008_hidden_crawl_targets.sql` — maps hidden target IDs to post_insight for delete flow

GIN indexes on `aspects` and `uap_metadata` JSONB. No FKs; soft links via `source_id` + `uap_metadata`.

---

## 6. Kafka I/O

| Topic | Direction | Key | Payload |
| --- | --- | --- | --- |
| `smap.collector.output` | consume | none | UAP v1.0 JSON (`UAPRecord.parse`) |
| `analytics.batch.completed` | publish | project_id | `InsightMessage[]` for batch |
| `analytics.insights.published` | publish | project_id | `InsightCard[]` (Phase 4+, mostly empty now) |
| `analytics.report.digest` | publish | project_id | `BIReportBundle` (Phase 5+, minimal now) |
| `analytics.crisis.alert` | publish (optional) | project_id | crisis alert payload (see §8) |

**Consumer**: group `analytics-service` (constant.py L28). Auto-commit disabled — manual offset commit after flush. `max_poll_records=6` default. Session 30s. Max poll interval 10 min (for ONNX time).

**Producer**: acks=all, gzip, idempotent, linger 100ms.

**ContractPublisher** (`internal/contract_publisher/usecase/usecase.py` L40–127):
- Buffer of (UAPRecord, InsightMessage) pairs.
- Auto-flush at `batch_size` (default 100, configurable).
- Consumer also calls **explicit flush after every `_persist_and_publish()`** (server.py L407–426). This is the fix for the prior "small E2E batches never publish" bug — do NOT remove that explicit call.
- Publish order enforced: batch.completed → insights.published → report.digest (`publish_order.py`).

---

## 7. HTTP API (analysis-api)

| Route | Method | Scope params | Purpose |
| --- | --- | --- | --- |
| `/health` | GET | — | liveness |
| `/ready` | GET | — | DB ping (5s cache); triggers mart refresh on schedule |
| `/api/v1/analytics/kpis` | GET | campaignId, sourceKind, projectIds, keywords | KPI summary card |
| `/api/v1/analytics/platforms` | GET | same | Platform distribution |
| `/api/v1/analytics/sentiment` | GET | same | Sentiment pie |
| `/api/v1/analytics/keywords` | GET | + limit (1–100) | Top keywords |
| `/api/v1/analytics/posts` | GET | + platform, sentiment, sort (engagement/time/virality), limit, offset, contentType | Posts table |
| `/api/v1/analytics/posts/export` | GET | same as posts | CSV/SVG export |
| `/api/v1/analytics/project-stats` | GET | same | Per-project comparison |
| `/api/v1/analytics/heap` | GET | same | Advanced analytics heap |
| `/api/v1/internal/analytics/hidden-crawl-targets` | POST | body: target_id, data_source_id, reason, hidden_by | Internal hide (called by ingest-srv) |

**Scope conventions**:
- `sourceKind`: `all | focused_page | focused_profile | keyword`
- `projectIds`: comma-separated UUID list
- `contentType`: `all | text | image | video | mixed`

**Statement timeout guard** (api/main.py L93–109):
- Server side: `statement_timeout_ms` default 25 000 (env `ANALYTICS_DATABASE_STATEMENT_TIMEOUT_MS`). 504 if exceeded.
- App side: `query_timeout_ms` capped to statement timeout.
- **Negative cache** for timeouts (`analytics_service.py` L247–263): campaigns that timed out cached 5 min to fail fast. Gotcha: blocks fast recovery after query opt — invalidate manually if needed.

**Hidden-crawl-targets**: requires `X-Internal-Key` header. Soft-delete via status flag in `uap_metadata->>'target_id'` match. Used by ingest-srv stalker flush.

---

## 8. Project-srv Integration + Crisis Push

**Client**: `internal/http/project_client.py` (async HTTP, header `X-Internal-Key`).

| Method | Endpoint | Returns | Cache |
| --- | --- | --- | --- |
| `get_crisis_runtime_config(project_id)` | `GET /api/v1/internal/projects/{id}/crisis-config` | `ProjectCrisisRuntimeConfig` | 60s |
| `get_ontology_runtime_config(project_id)` | `GET /api/v1/internal/projects/{id}/ontology-rules` | `ProjectOntologyRuntimeConfig` | 60s |
| `apply_crisis_runtime(project_id, crisis_level, reason, event_ref)` | `POST /api/v1/internal/projects/{id}/crisis-runtime/apply` | `CrisisRuntimeApplyResult` | no cache |

**Auto-apply crisis** (server.py L575–647), gated by env `ANALYTICS_ENABLE_CRISIS_RUNTIME_APPLY=true`:
1. After each batch, `_maybe_apply_crisis_runtime(result, runtime_config)` (L343).
2. Map `CrisisLevel` → status `CRITICAL/WARNING/WATCH/NORMAL` (L501–511).
3. Check Redis `smap:crisis:runtime-state:{project_id}`; skip if unchanged.
4. Acquire distributed lock `smap:crisis:runtime-lock:{project_id}` (45s TTL, NX).
5. Call project-srv `apply_crisis_runtime`.
6. Update Redis state.
7. Adaptive cooldown from `crisis_config.response_policy.adaptive_crawl.cooldown_minutes` (default 30 min).

**Crisis alert publish** (server.py L742–844):
- Topic: env `ANALYTICS_CRISIS_ALERT_TOPIC` (default `analytics.crisis.alert`).
- Trigger level from `crisis_config.response_policy.notification.trigger_level` (default WARNING).
- Repeat cooldown from notification policy (default 60 min).
- Payload: `alert_type=CRISIS_ALERT`, severity, level, affected_aspects[], sample_mentions[], run_id.
- `ops_alert_on_critical` flag sends to ops channel on CRITICAL.

---

## 9. Health / Probes

| Probe | Mechanism |
| --- | --- |
| Startup (consumer) | File `/tmp/healthy` written after Kafka consumer ready (server.py L134) |
| Liveness (consumer) | File exists check; removed on SIGTERM (L467) |
| Readiness (api) | `GET /ready` — async DB ping with 5s cache (api/main.py L275–279). 200 if pool alive; 503 otherwise. |
| Mart refresh | Triggered by readiness probe every `ANALYTICS_MART_REFRESH_SECONDS` (default 300). Statement timeout `ANALYTICS_MART_REFRESH_TIMEOUT_MS` (default 240 000). |

Consumer has no HTTP endpoint — file probe only.

---

## 10. Known Bugs / Fragile Spots

| Area | Issue | Mitigation in place |
| --- | --- | --- |
| ContractPublisher | Previously flushed only at batch_size=100 → small E2E batches never emitted `analytics.batch.completed`. | Explicit flush after each consume loop (server.py L407–426). DO NOT remove. |
| Sentiment schema | 3-class hardcoded but DB column is VARCHAR(20). | Safe today; coordinate migration if labels expand. |
| Negative cache | 5-min TTL on timeout campaigns blocks fast recovery after query opt. | Manual invalidate if needed. |
| Hidden-crawl-targets mart | `migration/007` hardcodes regex for logistics + HR/CRM domains. Adding domains requires SQL migration. | Ontology-driven filtering not yet implemented. |
| ONNX poll interval | If ONNX batch > 10 min, rebalance mid-batch. | Lower `ANALYTICS_CONSUME_BATCH_SIZE` instead of raising timeout. |
| post_insight dedup | Mart `DISTINCT ON (platform, source_id) ORDER BY updated_at DESC` — duplicate source_id without updated_at can lose data. | Ensure UAP source_id uniqueness upstream. |
| Sentiment timeout | Default `ANALYTICS_DATABASE_STATEMENT_TIMEOUT_MS=25000` may 504 on very large campaigns. | Bump to 120 000 ms in deploy (see SSOT). |
| Phase 4–6 features | enrichment/review/reporting/crisis flags default OFF; semantic enrichment is stub. | Don't claim crisis works end-to-end without enabling + testing. |

---

## 11. Dev / Test

```bash
uv sync                                        # install
make spacy-model                               # download xx_ent_wiki_sm
make run-consumer                              # or: uv run python -m apps.consumer.main
uv run python -m apps.api.main                 # API
make test                                      # 180 tests via pytest
make lint && make format                       # ruff + black
uv run python scripts/run_migration.py migration/004_optimize_post_insight_reads.sql
uv run python scripts/replay_batch.py <batch_file.json>   # replay from MinIO
```

**Build**: `scripts/Dockerfile.base` produces base image with PhoBERT model (~2 GB). `scripts/build-base.sh` and `scripts/build-consumer.sh` build and push. Tag pattern `<YYMMDD>-<HHMM>-<reason>`.

---

## 12. Config / Env

Priority: env (`ANALYTICS_*`) > `.env` > `config/config.yaml`.

| Var | Meaning | Default |
| --- | --- | --- |
| `ANALYTICS_DATABASE_URL` | asyncpg PG URL | required |
| `ANALYTICS_DATABASE_STATEMENT_TIMEOUT_MS` | PG statement timeout | 25 000 |
| `ANALYTICS_DATABASE_IDLE_TX_TIMEOUT_MS` | Idle tx timeout | 30 000 |
| `ANALYTICS_QUERY_TIMEOUT_MS` | API query timeout | 25 000 |
| `ANALYTICS_KAFKA_BOOTSTRAP_SERVERS` | brokers | `localhost:9092` |
| `ANALYTICS_CONSUME_BATCH_SIZE` | Kafka max_poll_records | 6 |
| `ANALYTICS_CONSUME_TIMEOUT_MS` | poll timeout | 1 000 |
| `ANALYTICS_OMP_NUM_THREADS` | BLAS/ONNX threads | 1 |
| `ANALYTICS_ONNX_INTRA_OP_THREADS` | ONNX intra-op | 2 |
| `ANALYTICS_ONNX_INTER_OP_THREADS` | ONNX inter-op | 1 |
| `ANALYTICS_MINIO_ENDPOINT` / `_ACCESS_KEY` / `_SECRET_KEY` | MinIO | empty |
| `ANALYTICS_ENABLE_CRISIS_RUNTIME_APPLY` | auto-apply crisis | false |
| `ANALYTICS_CRISIS_ALERT_TOPIC` | alert topic | `analytics.crisis.alert` |
| `ANALYTICS_MART_REFRESH_SECONDS` | mart refresh interval | 300 |
| `ANALYTICS_MART_REFRESH_TIMEOUT_MS` | mart refresh stmt timeout | 240 000 |
| `INTERNAL_KEY` / `INTERNAL_INTERNAL_KEY` | project-srv auth header | empty |
| `POD_NAME` | Kafka client_id | `analytics-consumer` |

`config.yaml` key sections: `database`, `kafka`, `contract_publisher` (batch_size, flush_interval_seconds), `pipeline` (feature flags — `enable_nlp` defaults false in file, must enable explicitly).

---

## 13. Pitfalls — DO NOT

1. Reset/replace `DomainRegistry` at runtime. Restart pod for ontology changes.
2. Change `contract_publisher.batch_size` without checking Kafka partition fan-in. Stalls if partition fills faster than flush.
3. Edit existing domain YAML in place. Use overlays.
4. Hardcode sentiment label strings outside `constant.py`. Use the enum + thresholds.
5. Drop `ANALYTICS_DATABASE_STATEMENT_TIMEOUT_MS` below 5 000.
6. Reduce `max_poll_interval_ms` below 300 000. ONNX needs the headroom.
7. Remove the explicit `ContractPublisher.flush()` call after `_persist_and_publish()`. That was the fix for "knowledge-srv indexed=0".
8. Edit `migration/007` regex without coordinating with ontology + downstream knowledge filters.
9. Treat hidden-crawl-targets endpoint as hard-delete. It's soft-delete only.
10. Disable Redis without rewriting crisis runtime state logic — Redis is the cross-pod source of truth and distributed lock.

**Coordination boundaries**:
- UAP schema change → coordinate with `ingest-srv` (producer) and `knowledge-srv` (downstream).
- Contract topic payload change → coordinate with `knowledge-srv` indexing pipeline.
- `analytics.crisis.alert` payload change → coordinate with `notification-srv` analytics bridge.

---

Last updated: 2026-06-06. Version: 0.1.0. Status: Phase 1 core, Phase 4–6 partially stubbed.
