# Phase 6: Code Plan — Legacy Cleanup

**Ref:** `documents/master-proposal.md` (Phase 6)
**Convention:** `documents/convention/`
**Depends on:** Phase 1-5 (completed) + 2 weeks verification period

---

## 0. SCOPE

Remove toàn bộ legacy schema, code, và infrastructure sau khi verify schema mới hoạt động ổn định.

**Điều kiện tiên quyết (MANDATORY):**
- Schema mới `analytics.post_analytics` đã chạy ổn định ≥ 2 tuần
- Không có incident liên quan đến data integrity
- Knowledge Service consume Kafka topic thành công
- Downstream services đã migrate sang schema mới

**Phase 6 sẽ cleanup:**

1. Database: DROP legacy schema `schema_analyst.analyzed_posts`
2. Code: Remove Event Envelope parsing logic
3. Code: Remove deprecated fields và mappings
4. Infrastructure: Xóa legacy RabbitMQ queue
5. Config: Remove legacy queue config
6. Documentation: Update để reflect new architecture

**OUT OF SCOPE:**
- Không rollback được sau khi cleanup (one-way migration)
- Không cleanup nếu chưa đủ 2 tuần verify

---

## 1. FILE PLAN

### 1.1 Files xóa (DELETE)

| #   | File                                                               | Lý do                                                |
| --- | ------------------------------------------------------------------ | ---------------------------------------------------- |
| 1   | `migration/000_legacy_schema.sql` (if exists)                      | Legacy schema definition không còn cần               |
| 2   | `internal/analytics/delivery/rabbitmq/consumer/event_envelope.py`  | Event Envelope parser (replaced by UAP)              |
| 3   | `internal/analytics/delivery/rabbitmq/consumer/legacy_handler.py`  | Legacy handler cho queue cũ (if separated)           |
| 4   | `internal/model/event_envelope.py` (if exists)                     | Event Envelope type definitions                      |

### 1.2 Files sửa (MODIFY)

| #   | File                                                               | Thay đổi                                                                                      |
| --- | ------------------------------------------------------------------ | --------------------------------------------------------------------------------------------- |
| 1   | `config/config.yaml`                                               | Remove legacy queue `analytics.data.collected`                                                |
| 2   | `internal/analytics/type.py`                                       | Remove deprecated fields: `job_id`, `batch_index`, `task_type`, `keyword_source`, etc.       |
| 3   | `internal/analytics/delivery/rabbitmq/consumer/presenters.py`      | Remove Event Envelope mapping logic, chỉ giữ UAP mapping                                      |
| 4   | `internal/analytics/delivery/rabbitmq/consumer/handler.py`         | Remove fallback logic cho Event Envelope (if any)                                             |
| 5   | `internal/model/analyzed_post.py`                                  | Remove legacy columns mapping (if any ORM references to old schema)                           |
| 6   | `internal/analyzed_post/repository/postgre/analyzed_post.py`       | Remove references to old table `schema_analyst.analyzed_posts`                                |
| 7   | `internal/analyzed_post/repository/postgre/analyzed_post_query.py` | Remove legacy query builders (if any)                                                         |
| 8   | `README.md`                                                        | Update architecture diagram, remove references to Event Envelope                              |
| 9   | `documents/input_payload.md`                                       | Archive or update to reflect UAP only                                                         |
| 10  | `documents/output_payload.md`                                      | Archive or update to reflect Enriched Output only                                             |
| 11  | `.env.example` / deployment configs                                | Remove legacy queue environment variables                                                     |

### 1.3 Database Migrations (CREATE)

| #   | File                                  | Mục đích                                                |
| --- | ------------------------------------- | ------------------------------------------------------- |
| 1   | `migration/004_drop_legacy_schema.sql` | DROP TABLE + DROP SCHEMA (with backup instructions)     |
| 2   | `migration/004_rollback.sql`          | Rollback script (restore from backup) — safety measure |

---

## 2. CHI TIẾT TỪNG FILE

### 2.1 Database Migration: `migration/004_drop_legacy_schema.sql`

**CRITICAL: Backup trước khi chạy!**

```sql
-- ============================================================================
-- Migration 004: Drop Legacy Schema
-- ============================================================================
-- PREREQUISITE: 
--   1. Schema mới analytics.post_analytics đã chạy ổn định ≥ 2 tuần
--   2. Không còn service nào đọc/ghi schema_analyst.analyzed_posts
--   3. Đã backup toàn bộ data trong schema_analyst
--
-- BACKUP COMMAND (run before this migration):
--   pg_dump -h <host> -U <user> -d <database> -n schema_analyst -F c -f schema_analyst_backup_$(date +%Y%m%d).dump
--
-- ROLLBACK: Use migration/004_rollback.sql + restore from backup
-- ============================================================================

BEGIN;

-- Step 1: Verify no active connections to legacy table
DO $$
DECLARE
    active_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO active_count
    FROM pg_stat_activity
    WHERE query LIKE '%schema_analyst.analyzed_posts%'
      AND state = 'active'
      AND pid != pg_backend_pid();
    
    IF active_count > 0 THEN
        RAISE EXCEPTION 'Active connections detected on schema_analyst.analyzed_posts. Abort migration.';
    END IF;
END $$;

-- Step 2: Drop legacy table
DROP TABLE IF EXISTS schema_analyst.analyzed_posts CASCADE;

-- Step 3: Drop legacy schema (only if empty)
DO $$
DECLARE
    table_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO table_count
    FROM information_schema.tables
    WHERE table_schema = 'schema_analyst';
    
    IF table_count = 0 THEN
        DROP SCHEMA IF EXISTS schema_analyst CASCADE;
        RAISE NOTICE 'Schema schema_analyst dropped successfully';
    ELSE
        RAISE NOTICE 'Schema schema_analyst still contains % tables, not dropping', table_count;
    END IF;
END $$;

-- Step 4: Revoke permissions (if schema dropped)
-- REVOKE ALL ON SCHEMA schema_analyst FROM <app_user>;
-- (Uncomment and replace <app_user> if needed)

COMMIT;

-- ============================================================================
-- Verification Queries (run after migration)
-- ============================================================================
-- Check schema exists:
-- SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'schema_analyst';
-- Expected: 0 rows

-- Check table exists:
-- SELECT table_name FROM information_schema.tables WHERE table_schema = 'schema_analyst' AND table_name = 'analyzed_posts';
-- Expected: 0 rows

-- Check new schema is working:
-- SELECT COUNT(*) FROM analytics.post_analytics;
-- Expected: > 0 rows
```


---

### 2.2 Database Rollback: `migration/004_rollback.sql`

```sql
-- ============================================================================
-- Migration 004 Rollback: Restore Legacy Schema
-- ============================================================================
-- PREREQUISITE: 
--   1. Backup file exists: schema_analyst_backup_YYYYMMDD.dump
--   2. Decision to rollback has been made
--
-- RESTORE COMMAND:
--   pg_restore -h <host> -U <user> -d <database> -n schema_analyst schema_analyst_backup_YYYYMMDD.dump
--
-- WARNING: This will restore the old schema but NOT sync data from analytics.post_analytics
-- Manual data migration may be required if new records were created after cleanup
-- ============================================================================

BEGIN;

-- Step 1: Recreate schema (if dropped)
CREATE SCHEMA IF NOT EXISTS schema_analyst;

-- Step 2: Restore from backup (run pg_restore command above)
-- This script only prepares the environment

-- Step 3: Grant permissions
-- GRANT USAGE ON SCHEMA schema_analyst TO <app_user>;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA schema_analyst TO <app_user>;

COMMIT;

-- ============================================================================
-- Post-Rollback Actions
-- ============================================================================
-- 1. Re-enable legacy queue in config.yaml
-- 2. Restart Analysis Service
-- 3. Verify legacy pipeline works
-- 4. Decide on data sync strategy (analytics.post_analytics -> schema_analyst.analyzed_posts)
```

---

### 2.3 Config: `config/config.yaml` — Remove Legacy Queue

**Before (Phase 1-5):**

```yaml
rabbitmq:
  queues:
    # New UAP queue
    - name: "smap.collector.output"
      exchange: "smap.events"
      routing_key: "collector.output"
      handler_module: "internal.analytics.delivery.rabbitmq.consumer.handler"
      handler_class: "AnalyticsHandler"
      prefetch_count: 1
      enabled: true

    # Legacy queue (deprecated, kept for transition)
    - name: "analytics.data.collected"
      exchange: "smap.events"
      routing_key: "data.collected"
      handler_module: "internal.analytics.delivery.rabbitmq.consumer.legacy_handler"
      handler_class: "LegacyAnalyticsHandler"
      prefetch_count: 1
      enabled: false  # Disabled after migration
```

**After (Phase 6):**

```yaml
rabbitmq:
  queues:
    # UAP queue (only queue)
    - name: "smap.collector.output"
      exchange: "smap.events"
      routing_key: "collector.output"
      handler_module: "internal.analytics.delivery.rabbitmq.consumer.handler"
      handler_class: "AnalyticsHandler"
      prefetch_count: 1
      enabled: true
```

**Thay đổi:**
- Remove toàn bộ entry cho `analytics.data.collected`
- Remove references đến `legacy_handler` module

---

### 2.4 Code: `internal/analytics/type.py` — Remove Deprecated Fields

**Deprecated fields cần xóa:**

```python
# REMOVE THESE FIELDS from Input, AnalyticsResult, or any related types:

# Legacy Event Envelope fields
job_id: Optional[str] = None              # Replaced by ingest.batch.batch_id
batch_index: Optional[int] = None         # Replaced by ingest.batch metadata
task_type: Optional[str] = None           # Not used in UAP
keyword_source: Optional[str] = None      # Replaced by ingest.entity
crawled_at: Optional[datetime] = None     # Replaced by ingest.batch.received_at
pipeline_version: Optional[str] = None    # Replaced by provenance.pipeline
brand_name: Optional[str] = None          # Replaced by ingest.entity.brand
keyword: Optional[str] = None             # Replaced by ingest.entity.entity_name
```

**Action:**

1. Search toàn bộ codebase cho các fields này
2. Remove field definitions
3. Remove usages trong constructors, to_dict(), from_dict()
4. Update tests để không reference các fields này

**Example diff:**

```python
# Before
@dataclass
class AnalyticsResult:
    id: str
    project_id: str
    # ... other fields ...
    
    # Legacy fields
    job_id: Optional[str] = None
    batch_index: Optional[int] = None
    keyword: Optional[str] = None
    brand_name: Optional[str] = None

# After
@dataclass
class AnalyticsResult:
    id: str
    project_id: str
    # ... other fields ...
    
    # Legacy fields removed — use UAP metadata instead
```

---

### 2.5 Code: `internal/analytics/delivery/rabbitmq/consumer/presenters.py` — Remove Event Envelope Mapping

**Remove legacy mapping functions:**

```python
# REMOVE THESE FUNCTIONS:

def parse_event_envelope(raw_json: str) -> Dict[str, Any]:
    """Parse Event Envelope format (LEGACY)."""
    # ... old parsing logic ...

def map_event_envelope_to_input(envelope: Dict[str, Any]) -> Input:
    """Map Event Envelope to Analytics Input (LEGACY)."""
    # ... old mapping logic ...

def extract_meta_from_envelope(envelope: Dict[str, Any]) -> Dict[str, Any]:
    """Extract meta from Event Envelope (LEGACY)."""
    # ... old extraction logic ...
```

**Keep only UAP mapping:**

```python
# KEEP ONLY:

def map_uap_to_input(uap_record: UAPRecord) -> Input:
    """Map UAP Record to Analytics Input."""
    # ... UAP mapping logic (from Phase 1) ...
```

---

### 2.6 Code: `internal/analytics/delivery/rabbitmq/consumer/handler.py` — Remove Fallback Logic

**Remove Event Envelope fallback:**

```python
# REMOVE THIS PATTERN:

async def handle(self, message: IncomingMessage):
    """Handle incoming message."""
    try:
        # Try UAP first
        uap_record = self.uap_parser.parse(message.body)
        input_data = map_uap_to_input(uap_record)
    except UAPValidationError:
        # REMOVE THIS FALLBACK:
        # Fallback to Event Envelope
        envelope = parse_event_envelope(message.body)
        input_data = map_event_envelope_to_input(envelope)
    
    # Process...
```

**After cleanup:**

```python
async def handle(self, message: IncomingMessage):
    """Handle incoming message."""
    # Only UAP parsing, no fallback
    uap_record = self.uap_parser.parse(message.body)
    input_data = map_uap_to_input(uap_record)
    
    # Process...
```

---

### 2.7 Code: `internal/model/analyzed_post.py` — Remove Legacy Column References

**If ORM model has references to old schema:**

```python
# REMOVE any references like:

class AnalyzedPost(Base):
    __tablename__ = "analyzed_posts"
    __table_args__ = {"schema": "schema_analyst"}  # REMOVE THIS
    
    # ... columns ...
```

**Ensure only new schema is referenced:**

```python
class PostAnalytics(Base):
    __tablename__ = "post_analytics"
    __table_args__ = {"schema": "analytics"}  # Correct
    
    # ... columns ...
```

---

### 2.8 Infrastructure: RabbitMQ Queue Cleanup

**Manual steps (run after code deployment):**

```bash
# 1. Check queue status
rabbitmqadmin list queues name messages consumers

# 2. Verify no messages pending in legacy queue
# Expected: analytics.data.collected has 0 messages

# 3. Delete legacy queue
rabbitmqadmin delete queue name=analytics.data.collected

# 4. Delete legacy exchange bindings (if any)
rabbitmqadmin delete binding source=smap.events destination=analytics.data.collected destination_type=queue routing_key=data.collected

# 5. Verify cleanup
rabbitmqadmin list queues name | grep analytics.data.collected
# Expected: no output
```

---

### 2.9 Documentation: Update Architecture Docs

**Files to update:**

1. `README.md`:
   - Remove Event Envelope from architecture diagram
   - Update data flow to show only UAP → Kafka
   - Remove references to `schema_analyst`

2. `documents/input_payload.md`:
   - Archive old Event Envelope examples
   - Add note: "DEPRECATED: See UAP_INPUT_SCHEMA.md"

3. `documents/output_payload.md`:
   - Archive old flat DB schema
   - Add note: "DEPRECATED: See indexing_input_schema.md"

4. `documents/status.md`:
   - Update to reflect Phase 6 completion
   - Mark legacy components as "REMOVED"

**Example README.md update:**

```markdown
# Analysis Service

## Architecture (Updated Phase 6)

```
Collector → RabbitMQ (UAP) → Analysis Service → PostgreSQL (analytics.post_analytics)
                                               → Kafka → Knowledge Service
```

~~Old architecture (REMOVED):~~
~~Collector → RabbitMQ (Event Envelope) → Analysis Service → PostgreSQL (schema_analyst.analyzed_posts)~~
```

---

## 3. CLEANUP CHECKLIST

### 3.1 Pre-Cleanup Verification (MANDATORY)

- [ ] Schema mới `analytics.post_analytics` đã chạy ổn định ≥ 2 tuần
- [ ] Zero incidents liên quan đến data integrity
- [ ] Knowledge Service consume Kafka topic thành công
- [ ] Downstream services đã migrate sang schema mới
- [ ] Backup database đã được tạo: `schema_analyst_backup_YYYYMMDD.dump`
- [ ] Rollback plan đã được review và approved
- [ ] Stakeholders đã được thông báo về cleanup schedule

### 3.2 Database Cleanup

- [ ] Run backup command: `pg_dump -n schema_analyst ...`
- [ ] Verify backup file size > 0
- [ ] Run `migration/004_drop_legacy_schema.sql`
- [ ] Verify schema dropped: `SELECT * FROM information_schema.schemata WHERE schema_name = 'schema_analyst'` → 0 rows
- [ ] Verify new schema working: `SELECT COUNT(*) FROM analytics.post_analytics` → > 0 rows
- [ ] Test queries on new schema
- [ ] Monitor database performance after cleanup

### 3.3 Code Cleanup

- [ ] Delete `event_envelope.py` (if exists)
- [ ] Delete `legacy_handler.py` (if exists)
- [ ] Remove deprecated fields from `internal/analytics/type.py`
- [ ] Remove Event Envelope mapping from `presenters.py`
- [ ] Remove fallback logic from `handler.py`
- [ ] Remove legacy column references from ORM models
- [ ] Remove legacy query builders
- [ ] Search codebase for "event_envelope", "schema_analyst", "analyzed_posts" → no results
- [ ] Run linter: `ruff check .`
- [ ] Run type checker: `mypy .`

### 3.4 Config Cleanup

- [ ] Remove legacy queue from `config/config.yaml`
- [ ] Remove legacy queue env vars from `.env.example`
- [ ] Update deployment configs (Kubernetes, Docker Compose)
- [ ] Remove legacy queue from monitoring/alerting rules

### 3.5 Infrastructure Cleanup

- [ ] Verify legacy queue has 0 messages pending
- [ ] Delete legacy queue: `rabbitmqadmin delete queue name=analytics.data.collected`
- [ ] Delete legacy exchange bindings
- [ ] Verify queue deleted: `rabbitmqadmin list queues | grep analytics.data.collected` → no output
- [ ] Update RabbitMQ monitoring dashboards

### 3.6 Documentation Cleanup

- [ ] Update `README.md` architecture diagram
- [ ] Archive `documents/input_payload.md` (Event Envelope)
- [ ] Archive `documents/output_payload.md` (old schema)
- [ ] Update `documents/status.md` to reflect Phase 6 completion
- [ ] Update API documentation (if any)
- [ ] Update team wiki/confluence pages

### 3.7 Testing

- [ ] Unit tests pass: `pytest tests/`
- [ ] Integration tests pass with new schema only
- [ ] Send UAP message → verify processing works
- [ ] Query new schema → verify data correct
- [ ] Check Kafka topic → verify messages published
- [ ] Check Knowledge Service → verify consumption works
- [ ] Load test: verify performance acceptable
- [ ] Monitor logs for errors related to legacy code

---

## 4. ROLLBACK PLAN

**Trigger conditions:**
- Critical bug discovered in new schema
- Data integrity issues
- Performance degradation
- Downstream service failures

**Rollback steps:**

1. **Stop Analysis Service**
   ```bash
   kubectl scale deployment analysis-service --replicas=0
   ```

2. **Restore database**
   ```bash
   pg_restore -h <host> -U <user> -d <database> -n schema_analyst schema_analyst_backup_YYYYMMDD.dump
   ```

3. **Revert code changes**
   ```bash
   git revert <phase6_commit_hash>
   git push origin main
   ```

4. **Re-enable legacy queue**
   - Restore `analytics.data.collected` in `config.yaml`
   - Set `enabled: true`

5. **Recreate RabbitMQ queue**
   ```bash
   rabbitmqadmin declare queue name=analytics.data.collected durable=true
   rabbitmqadmin declare binding source=smap.events destination=analytics.data.collected routing_key=data.collected
   ```

6. **Deploy rollback**
   ```bash
   kubectl rollout restart deployment analysis-service
   ```

7. **Verify rollback**
   - Check legacy queue consuming messages
   - Check `schema_analyst.analyzed_posts` receiving inserts
   - Monitor logs for errors

8. **Post-rollback analysis**
   - Identify root cause
   - Fix issues
   - Plan re-attempt of Phase 6

---

## 5. RISK ASSESSMENT

| Risk                                      | Probability | Impact   | Mitigation                                                    |
| ----------------------------------------- | ----------- | -------- | ------------------------------------------------------------- |
| Data loss during schema drop              | LOW         | CRITICAL | Mandatory backup before cleanup, verify backup integrity      |
| Downstream service breaks                 | MEDIUM      | HIGH     | Verify all services migrated before cleanup, staged rollout   |
| Rollback fails                            | LOW         | HIGH     | Test rollback procedure in staging, keep backup for 30 days   |
| Hidden dependencies on legacy schema      | MEDIUM      | MEDIUM   | Comprehensive code search, monitor logs after cleanup         |
| Performance issues after cleanup          | LOW         | MEDIUM   | Monitor database performance, have rollback ready             |
| Legacy queue still receiving messages     | LOW         | MEDIUM   | Verify Collector migrated to UAP, check queue before deletion |
| Team confusion about new architecture     | MEDIUM      | LOW      | Update documentation, conduct team training session           |
| Monitoring/alerting breaks                | MEDIUM      | LOW      | Update monitoring configs before cleanup                      |

---

## 6. COMMUNICATION PLAN

### 6.1 Pre-Cleanup (1 week before)

**Audience:** Engineering team, DevOps, Product

**Message:**
```
Subject: [ACTION REQUIRED] Analysis Service Phase 6 Cleanup - Legacy Schema Removal

Team,

We will be removing the legacy schema `schema_analyst.analyzed_posts` and Event Envelope support on [DATE].

PREREQUISITES COMPLETED:
✅ New schema analytics.post_analytics running stable for 2+ weeks
✅ Zero data integrity incidents
✅ Knowledge Service consuming Kafka successfully
✅ All downstream services migrated

WHAT WILL BE REMOVED:
- Database: schema_analyst.analyzed_posts table
- Queue: analytics.data.collected
- Code: Event Envelope parsing logic

WHAT YOU NEED TO DO:
- Verify your service is NOT using schema_analyst
- Verify your service is NOT consuming analytics.data.collected queue
- Update any hardcoded references to old schema

ROLLBACK PLAN:
- Database backup will be taken before cleanup
- Rollback procedure tested in staging
- Rollback can be executed within 30 minutes if needed

Questions? Reply to this thread or ping #analysis-service channel.
```

### 6.2 During Cleanup

**Audience:** Engineering team, DevOps

**Message:**
```
Subject: [IN PROGRESS] Analysis Service Phase 6 Cleanup

Phase 6 cleanup in progress:
⏳ Database backup: DONE
⏳ Schema drop: IN PROGRESS
⏳ Code deployment: PENDING
⏳ Queue deletion: PENDING

ETA: 30 minutes

Monitoring: [link to dashboard]
```

### 6.3 Post-Cleanup

**Audience:** Engineering team, DevOps, Product

**Message:**
```
Subject: [COMPLETED] Analysis Service Phase 6 Cleanup

Phase 6 cleanup completed successfully! 🎉

REMOVED:
✅ Legacy schema schema_analyst.analyzed_posts
✅ Legacy queue analytics.data.collected
✅ Event Envelope parsing code

CURRENT STATE:
✅ New schema analytics.post_analytics operational
✅ UAP input format only
✅ Kafka output to Knowledge Service
✅ All tests passing
✅ Zero errors in logs

NEXT STEPS:
- Monitor for 24 hours
- Backup retained for 30 days (rollback available)
- Documentation updated

Thank you for your support during this migration!
```

---

## 7. MONITORING & ALERTS

### 7.1 Metrics to Monitor (24 hours post-cleanup)

| Metric                                    | Threshold | Alert Level |
| ----------------------------------------- | --------- | ----------- |
| Error rate in Analysis Service            | > 1%      | CRITICAL    |
| Message processing latency                | > 5s      | WARNING     |
| Database query latency                    | > 500ms   | WARNING     |
| Kafka publish success rate                | < 99%     | CRITICAL    |
| Knowledge Service consumption lag         | > 1000    | WARNING     |
| Disk space (after schema drop)            | Check     | INFO        |
| CPU/Memory usage                          | Check     | INFO        |
| Number of records in analytics.post_analytics | Increasing | INFO    |

### 7.2 Log Patterns to Watch

```bash
# Errors related to legacy schema
grep -i "schema_analyst" /var/log/analysis-service/*.log

# Errors related to Event Envelope
grep -i "event_envelope" /var/log/analysis-service/*.log

# Errors related to legacy queue
grep -i "analytics.data.collected" /var/log/analysis-service/*.log

# Database errors
grep -i "relation.*does not exist" /var/log/analysis-service/*.log

# Expected: No results for all above
```

---

## 8. SUCCESS CRITERIA

Phase 6 is considered successful when:

- [ ] Legacy schema `schema_analyst.analyzed_posts` dropped successfully
- [ ] Legacy queue `analytics.data.collected` deleted successfully
- [ ] All legacy code removed from codebase
- [ ] All tests passing
- [ ] Zero errors in logs for 24 hours post-cleanup
- [ ] New schema `analytics.post_analytics` receiving inserts normally
- [ ] Kafka topic `smap.analytics.output` receiving messages normally
- [ ] Knowledge Service consuming messages successfully
- [ ] Database disk space reduced (verify cleanup freed space)
- [ ] Documentation updated to reflect new architecture
- [ ] Team trained on new architecture
- [ ] Monitoring dashboards updated
- [ ] No rollback required

---

## 9. POST-CLEANUP TASKS

### 9.1 Immediate (Day 1)

- [ ] Monitor metrics dashboard continuously
- [ ] Check logs every 2 hours
- [ ] Verify Kafka message flow
- [ ] Verify Knowledge Service indexing
- [ ] Run smoke tests

### 9.2 Short-term (Week 1)

- [ ] Daily log review
- [ ] Weekly performance report
- [ ] Verify backup retention policy
- [ ] Update team documentation
- [ ] Conduct retrospective meeting

### 9.3 Long-term (Month 1)

- [ ] Delete backup after 30 days (if no issues)
- [ ] Archive Phase 6 documentation
- [ ] Update disaster recovery procedures
- [ ] Plan next optimization phase

---

## 10. LESSONS LEARNED (Template)

**To be filled after Phase 6 completion:**

### What Went Well
- 

### What Could Be Improved
- 

### Action Items
- 

### Recommendations for Future Migrations
- 

---

## 11. TIMELINE

| Task                                  | Estimate     | Owner   |
| ------------------------------------- | ------------ | ------- |
| Pre-cleanup verification              | 1 day        | DevOps  |
| Database backup                       | 30 minutes   | DevOps  |
| Code cleanup (delete files)           | 2 hours      | Dev     |
| Code cleanup (modify files)           | 4 hours      | Dev     |
| Config cleanup                        | 1 hour       | DevOps  |
| Testing (unit + integration)          | 2 hours      | Dev     |
| Code review                           | 1 hour       | Team    |
| Deployment to staging                 | 30 minutes   | DevOps  |
| Staging verification                  | 2 hours      | QA      |
| Database migration (production)       | 1 hour       | DevOps  |
| Code deployment (production)          | 30 minutes   | DevOps  |
| Infrastructure cleanup (RabbitMQ)     | 30 minutes   | DevOps  |
| Documentation update                  | 2 hours      | Dev     |
| Post-cleanup monitoring (24h)         | 1 day        | DevOps  |
| **Total**                             | **~3 days**  |         |

**Recommended schedule:**
- Day 1: Pre-cleanup verification + backup + code cleanup + testing
- Day 2: Deployment + infrastructure cleanup + monitoring
- Day 3: Continued monitoring + documentation

---

## 12. DEPENDENCIES

### 12.1 External Dependencies

- [ ] Collector service migrated to UAP format
- [ ] Knowledge Service consuming Kafka topic
- [ ] Dashboard/Reporting services migrated to new schema
- [ ] Alert Service migrated to new schema
- [ ] Any other downstream consumers identified and migrated

### 12.2 Internal Dependencies

- [ ] Phase 1 (UAP Parser) completed
- [ ] Phase 2 (Kafka Publisher) completed
- [ ] Phase 3 (DB Migration) completed
- [ ] Phase 4 (Business Logic) completed
- [ ] Phase 5 (Data Mapping) completed
- [ ] 2 weeks verification period completed
- [ ] Zero critical bugs in new implementation

---

## 13. CONVENTION ADHERENCE

### 13.1 Code Cleanup Standards

- **File deletion:** Use `git rm` to properly remove files from version control
- **Deprecation comments:** Remove all `# DEPRECATED` comments after cleanup
- **Import cleanup:** Run `ruff check --select F401` to find unused imports
- **Dead code:** Run `vulture` to find unreachable code
- **Type checking:** Ensure `mypy` passes after field removals

### 13.2 Database Standards

- **Migration naming:** `00X_action_description.sql` format
- **Rollback scripts:** Always provide rollback for destructive operations
- **Backup verification:** Test restore procedure before production cleanup
- **Transaction safety:** Use `BEGIN/COMMIT` blocks for atomic operations

### 13.3 Documentation Standards

- **Architecture diagrams:** Update to reflect current state only
- **Deprecation notices:** Remove after cleanup, don't leave stale warnings
- **Code comments:** Remove references to legacy components
- **API docs:** Update to show only current endpoints/formats

---

**END OF PHASE 6 CODE PLAN**
