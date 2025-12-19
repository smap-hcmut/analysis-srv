# Proposal: Establish Phase 0 Foundation

## Goal
Establish the architectural foundation (Phase 0) for the Analytics Engine service, ensuring a robust, scalable, and maintainable codebase that follows the standard project structure pattern.

## Context
The project uses a standardized structure with `cmd/` for entry points, `internal/` for implementation, `core/` for shared functionality, and `services/` for business logic. This Phase 0 establishes the foundation following this pattern.

## What Changes
This proposal introduces the initial project structure and foundational components:
1.  **Directory Structure**: Create `cmd/analytics_api/`, `cmd/analytics_consumer/`, `internal/api/`, `internal/consumers/`, with existing `core/` for shared functionality.
2.  **Development Environment**: Set up Docker Compose for Postgres, Redis, MinIO, and RabbitMQ.
3.  **Dependency Management**: Configure `uv` for Python dependency management with `pyproject.toml`.
4.  **Database Management**: Set up Alembic for migrations and define the initial `post_analytics` schema in `core/models.py`.
5.  **Entry Points**: Create entry points in `cmd/` that load config, initialize instances, and start services.
6.  **Internal Implementation**: Create route registration in `internal/api/` and consumer registration in `internal/consumers/`.

## Links
- [Architecture Document](document/architecture.md)
- [Implementation Plan](document/implement_plan.md)
