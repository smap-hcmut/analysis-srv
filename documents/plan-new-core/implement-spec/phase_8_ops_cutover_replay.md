# Phase 8 - Ops, Cutover, Replay

## Objective

Hoan thien tooling van hanh, cli commands, replay va cutover support.

## Function-level mapping

| Target file (analysis-srv) | Function can implement | Match tu smap-analyse | Notes |
|---|---|---|---|
| `apps/consumer/main.py` | `main()` | `NEW` + align voi existing main | Entry point cho consumer runtime |
| `internal/runtime/delivery/cli/app.py` | `_settings_from_args(args)` | `smap/cli/app.py::_settings_from_args` (L11) | Build runtime settings from CLI |
| `internal/runtime/delivery/cli/app.py` | `cmd_doctor(args)` | `smap/cli/app.py::cmd_doctor` (L50) | Runtime doctor command |
| `internal/runtime/delivery/cli/app.py` | `cmd_validate_batch(args)` | `smap/cli/app.py::cmd_validate_batch` (L62) | Validation command |
| `internal/runtime/delivery/cli/app.py` | `cmd_run_pipeline(args)` | `smap/cli/app.py::cmd_run_pipeline` (L69) | Full pipeline command |
| `internal/runtime/delivery/cli/app.py` | `build_parser()` | `smap/cli/app.py::build_parser` (L77) | CLI parser |
| `internal/runtime/usecase/replay.py` | `replay_run(run_id, source, mode='dry-run')` | `NEW` | Replay support for incidents |
| `internal/runtime/usecase/cutover.py` | `run_shadow_compare(old_output, new_output)` | `NEW` | Shadow mode compare |
| `internal/runtime/usecase/cutover.py` | `switch_publish_mode(mode)` | `NEW` | Toggle shadow/canary/full |

## Deliverables

- CLI ops commands.
- Replay tool.
- Cutover toggles.

## Exit criteria

- Oncall runbook execute duoc tren staging.
- Replay deterministic test pass.
