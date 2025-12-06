# Capability: foundation

## ADDED Requirements

### Requirement: Timezone-aware datetimes in database models

All database models MUST use timezone-aware datetime objects (UTC) instead of deprecated naive `datetime.utcnow()`. Models SHALL use `datetime.now(timezone.utc)` for all timestamp operations and MUST NOT use `datetime.utcnow()` (deprecated in Python 3.12).

**Rationale:** Python 3.12 deprecates `datetime.utcnow()` (removed in 3.14). All datetime operations must use explicit UTC timezone.

#### Scenario: Model creates timestamp with explicit UTC timezone

**Given:**

- Model has timestamp field (e.g., `created_at`, `analyzed_at`)
- Python version is 3.12+

**When:**

- Record is created in database

**Then:**

- Timestamp uses `datetime.now(timezone.utc)` (not `datetime.utcnow()`)
- No deprecation warnings in test output
- Timezone is explicitly UTC (not naive)

**Acceptance:**

```python
# models/database.py
from datetime import datetime, timezone

class PostAnalytics(Base):
    analyzed_at = Column(
        TIMESTAMP,
        default=lambda: datetime.now(timezone.utc)  # Timezone-aware
    )

class CrawlError(Base):
    created_at = Column(
        TIMESTAMP,
        default=lambda: datetime.now(timezone.utc)  # Timezone-aware
    )
```

**Validation:**

```bash
# Must pass with no datetime warnings
pytest tests/ -W error::DeprecationWarning
```

---

### Requirement: Timezone-aware datetime in repositories

Repository layer MUST create timestamps using timezone-aware datetime when saving records. Repositories SHALL use `datetime.now(timezone.utc)` when setting timestamp fields and MUST NOT use `datetime.utcnow()`.

#### Scenario: Repository saves record with UTC timestamp

**Given:**

- Repository saves error record or analytics record
- Python version is 3.12+

**When:**

- `save()` method is called

**Then:**

- `created_at` timestamp uses `datetime.now(timezone.utc)`
- No `DeprecationWarning` is raised
- Timestamp is timezone-aware (UTC)

**Acceptance:**

```python
# repository/crawl_error_repository.py
from datetime import datetime, timezone

def save(self, error_data: Dict[str, Any]) -> CrawlError:
    error_record = CrawlError(
        # ...
        created_at=datetime.now(timezone.utc),  # Not datetime.utcnow()
    )
```

**Validation:**

```bash
pytest tests/test_repositories/ -W error::DeprecationWarning
# Must pass with 0 warnings
```

---

### Requirement: SQLAlchemy 2.0 compatible imports

Database models MUST import `declarative_base` from `sqlalchemy.orm` instead of deprecated `sqlalchemy.ext.declarative` module. Models SHALL use `from sqlalchemy.orm import declarative_base` and MUST NOT import from `sqlalchemy.ext.declarative`.

**Rationale:** SQLAlchemy 2.0 moved declarative_base to new location to avoid deprecation warnings.

#### Scenario: Models import declarative_base without deprecation warning

**Given:**

- SQLAlchemy version is 2.0+
- Models file uses declarative base

**When:**

- Models are imported

**Then:**

- Import uses `from sqlalchemy.orm import declarative_base`
- No `MovedIn20Warning` is raised
- Models function correctly

**Acceptance:**

```python
# models/database.py - BEFORE
from sqlalchemy.ext.declarative import declarative_base  # DEPRECATED

# models/database.py - AFTER
from sqlalchemy.orm import declarative_base  # CORRECT
```

**Validation:**

```bash
pytest tests/test_models/ -v
# Must show no MovedIn20Warning
```

---

### Requirement: Indexed project_id column in post_analytics table

The `post_analytics` table MUST have an index on the `project_id` column to support efficient dashboard queries filtering by project. The index SHALL be created using `CREATE INDEX CONCURRENTLY` to avoid blocking writes and MUST be named `idx_post_analytics_project_id`.

**Rationale:**

- Dashboard queries frequently filter by `project_id`
- Without index, queries require sequential scan (2-5 seconds for 100K rows)
- With index, queries use index scan (10-50ms)

#### Scenario: Query uses index for project_id lookup

**Given:**

- `post_analytics` table has 100,000 rows
- Index `idx_post_analytics_project_id` exists
- Query filters by `project_id`

**When:**

- Query executes: `SELECT * FROM post_analytics WHERE project_id = 'uuid'`

**Then:**

- Query plan shows "Index Scan using idx_post_analytics_project_id"
- Query completes in <100ms (not 2-5 seconds)
- Index is created with CONCURRENTLY option (non-blocking)

**Acceptance:**

```sql
-- Migration creates index
CREATE INDEX CONCURRENTLY idx_post_analytics_project_id
ON post_analytics (project_id);

-- Query plan verification
EXPLAIN ANALYZE
SELECT * FROM post_analytics WHERE project_id = 'uuid-here';

-- Should show:
-- Index Scan using idx_post_analytics_project_id on post_analytics
-- (cost=0.42..8.44 rows=1 width=...)
```

**Migration:**

```python
# migrations/versions/xxx_add_project_id_index.py
def upgrade() -> None:
    op.create_index(
        "idx_post_analytics_project_id",
        "post_analytics",
        ["project_id"],
        postgresql_concurrently=True,  # Non-blocking
    )

def downgrade() -> None:
    op.drop_index("idx_post_analytics_project_id", table_name="post_analytics")
```

**Performance Impact:**

- **Query time:** 2000ms → 10ms (200x improvement)
- **Storage:** ~5 MB per 100K rows
- **Write penalty:** <5% slower inserts (acceptable trade-off)

---

## Cross-References

- **Related to:** `service_lifecycle` (consumer must work with updated models)
- **Related to:** `monitoring` (metrics track database performance)
