"""Reporting interface — IReportingUseCase Protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from internal.reporting.type import ReportingInput, ReportingOutput


@runtime_checkable
class IReportingUseCase(Protocol):
    def report(self, inp: "ReportingInput") -> "ReportingOutput":
        """Assemble MartBundle, build BI reports, and produce Layer 1 + 2 payloads."""
        ...


__all__ = ["IReportingUseCase"]
