# Implementation Tasks

## 1. Remove API Code

- [x] 1.1 Delete `command/api/` directory
- [x] 1.2 Delete `internal/api/` directory
- [x] 1.3 Delete `tests/storage/test_api_swagger.py`
- [x] 1.4 Delete `tests/storage/test_json_format_validation.py`
- [x] 1.5 Delete `tests/integration/test_api_integration.py`

## 2. Update Configuration

- [x] 2.1 Remove API settings from `core/config.py` (`api_host`, `api_port`, `api_reload`)
- [x] 2.2 Remove API environment variables from `.env.example`
- [x] 2.3 Remove `run-api` command and help text from `Makefile`

## 3. Update Documentation

- [x] 3.1 Update `document/architecture.md` - Remove API references
- [x] 3.2 Update `document/analytic_orchestrator.md` - Remove API entry point
- [x] 3.3 Update `openspec/project.md` - Remove API from architecture overview

## 4. Validation

- [x] 4.1 Run `make run-consumer` to verify consumer still works
- [x] 4.2 Run `make test` to verify remaining tests pass
- [x] 4.3 Verify no remaining references to `internal.api` in codebase
