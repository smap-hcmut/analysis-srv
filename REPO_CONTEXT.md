# Repository Context

## Name
analysis-srv

## Purpose
SMAP analytics engine. It consumes collector events from Kafka, runs NLP pipeline stages (preprocess, intent, keywords, sentiment, impact), stores results in PostgreSQL, and publishes enriched events back to Kafka.

## Primary Stack
- Python 3.12+
- uv (dependency and run)
- aiokafka
- SQLAlchemy async
- PhoBERT, spaCy, YAKE

## Main Entrypoints
- Consumer: `apps.consumer.main`
- Typical local run: `make run-consumer`

## Important Commands
- Install deps: `make install` or `uv sync`
- Run consumer: `make run-consumer`
- Tests: `make test`
- Lint/format: `make lint`, `make format`

## External Dependencies
- Kafka (input/output topics)
- PostgreSQL
- Optional: Redis, MinIO

## Notes
- Current README indicates API/metrics layer is planned; active runtime is Kafka consumer.
- Config source: `config/config.yaml` with optional env overrides.
