#!/bin/bash
# Per-project chunked DELETE on analysis.post_insight for the stale slice
# captured by migration 022. Idempotent — re-running while consumers ingest
# new data is safe; rows that no longer match the stale list are skipped.
#
# Pace: 2 000 rows per chunk, 300 ms sleep between chunks. With kine sharing
# the same Postgres, the 2026-06-09 outage taught us a single bulk DELETE on
# this table starves the K3s control plane. The throttle keeps WAL pressure
# bounded.
#
# Expects the snapshot table from migration 022 to exist:
#   SELECT COUNT(*) FROM analysis.stale_project_ids;
#
# Usage (run on the postgres VM):
#   ./purge_stale_post_insight.sh
#   tail -f /tmp/purge_post_insight.log

set -uo pipefail
LOG=/tmp/purge_post_insight.log
PSQL() { sudo -n docker exec pg15_prod psql -U postgres -d smap -tA -P pager=off -c "$1"; }

echo "[$(date '+%F %T')] purge start" >>"$LOG"

mapfile -t STALE < <(PSQL "SELECT project_id FROM analysis.stale_project_ids ORDER BY project_id")
echo "[$(date '+%F %T')] ${#STALE[@]} stale project ids" >>"$LOG"

grand_total=0
for pid in "${STALE[@]}"; do
  echo "[$(date '+%F %T')] project=$pid begin" >>"$LOG"
  project_total=0
  chunk=0
  while :; do
    chunk=$((chunk+1))
    rows=$(PSQL "DELETE FROM analysis.post_insight WHERE id IN (SELECT id FROM analysis.post_insight WHERE project_id='$pid' LIMIT 2000) RETURNING 1" 2>>"$LOG" | wc -l | tr -d ' ')
    project_total=$((project_total + rows))
    if [ "$rows" -eq 0 ]; then
      echo "[$(date '+%F %T')] project=$pid done chunks=$chunk rows=$project_total" >>"$LOG"
      break
    fi
    if [ $((chunk % 10)) -eq 0 ]; then
      echo "[$(date '+%F %T')] project=$pid chunk=$chunk project_total=$project_total" >>"$LOG"
    fi
    sleep 0.3
  done
  grand_total=$((grand_total + project_total))
done

echo "[$(date '+%F %T')] purge complete grand_total=$grand_total" >>"$LOG"
echo "[$(date '+%F %T')] VACUUM ANALYZE start" >>"$LOG"
PSQL "VACUUM (ANALYZE) analysis.post_insight" >>"$LOG" 2>&1 || true
echo "[$(date '+%F %T')] done" >>"$LOG"
