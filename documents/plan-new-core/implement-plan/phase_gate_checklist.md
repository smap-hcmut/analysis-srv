# Phase Gate Checklist

Checklist bat buoc truoc khi close moi phase.

## A. Scope va design

- [ ] Scope phase da duoc approve.
- [ ] ADR/Design note da cap nhat.
- [ ] Mapping impact den downstream contracts da duoc review.

## B. Code va architecture

- [ ] Code moi tuan thu module convention (`interface.py`, `type.py`, `constant.py`, `errors.py`, `usecase/`, `delivery/`, `repository/`).
- [ ] Khong co business logic trong delivery/repository.
- [ ] `usecase/new.py` chi la factory.

## C. Test

- [ ] Unit test pass.
- [ ] Integration test cho flow phase pass.
- [ ] Regression test voi sample dataset pass.

## D. Runtime quality

- [ ] Structured logs co `trace_id`, `project_id`, `campaign_id`, `run_id`.
- [ ] Error budget phase trong nguong cho phep.
- [ ] Monitoring/dashboard da cap nhat.

## E. Documentation

- [ ] Plan docs cua phase da cap nhat status.
- [ ] Runbook/troubleshooting da cap nhat.
- [ ] Backlog phase tiep theo da duoc refine.

## F. Exit criteria

- [ ] Stakeholders sign-off.
- [ ] Khong con blocker P0/P1.
- [ ] Co rollback strategy neu release ngay sau phase.
