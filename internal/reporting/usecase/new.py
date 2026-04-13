"""new.py — factory for ReportingUseCase."""

from __future__ import annotations

from internal.reporting.usecase.usecase import ReportingUseCase


def new_reporting_usecase() -> ReportingUseCase:
    """Instantiate and return a ReportingUseCase (no external dependencies)."""
    return ReportingUseCase()


__all__ = ["new_reporting_usecase"]
