# Phase 8 - Cutover and Handover

## Muc tieu

Chuyen doi an toan sang pipeline moi voi rui ro thap va rollback ro rang.

## Cong viec chinh

1. Shadow run:
   - Chay song song pipeline cu/moi.
   - So sanh outputs va alerts.
2. Canary release:
   - Bat cho nhom projects pilot.
   - Theo doi quality gates trong 1-2 tuan.
3. Full cutover:
   - Route 100% traffic.
   - Monitor sat 72h dau.
4. Handover:
   - Training cho team van hanh.
   - Chot SOP + runbook + dashboard links.

## Deliverables

- Cutover report.
- Rollback playbook da duoc dien tap.
- Handover checklist da ky.

## Test/validation

- Canary success criteria pass.
- Rollback drill pass.
- Post-cutover incident review = none hoac minor.

## Exit criteria

- Production on dinh sau cutover window.
- Stakeholders sign-off va close migration.
