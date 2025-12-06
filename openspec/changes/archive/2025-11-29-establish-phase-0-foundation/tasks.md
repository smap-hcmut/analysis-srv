# Tasks: Phase 0 Foundation

- [x] **Project Setup** <!-- id: 0 -->

  - [x] Initialize Git repository structure (folders, .gitignore, README) <!-- id: 1 -->
  - [x] Configure `uv` (`pyproject.toml`) with dependencies <!-- id: 2 -->
  - [x] Create `docker-compose.dev.yml` (Postgres, Redis, MinIO) <!-- id: 3 -->
  - [x] Create `Makefile` for common command <!-- id: 4 -->
  - [x] Create `app/api/main.py` <!-- id: 5 -->
  - [x] Create `app/consumers/main.py` <!-- id: 6 -->

- [x] **Database Setup** <!-- id: 7 -->

  - [x] Initialize Alembic for Postgres (`alembic init migrations`) <!-- id: 8 -->
  - [x] Configure `alembic.ini` and `env.py` <!-- id: 9 -->
  - [x] Create initial migration script (`001_create_post_analytics.sql`) <!-- id: 10 -->

- [x] **Verification** <!-- id: 11 -->
  - [x] Verify `docker-compose up` works <!-- id: 12 -->
  - [x] Verify Alembic migrations apply successfully <!-- id: 13 -->
  - [x] Verify `uv run app/api/main.py` works <!-- id: 14 -->
  - [x] Verify `uv run app/consumers/main.py` works <!-- id: 15 -->
  - [x] Remove unused files and folders <!-- id: 16 -->
