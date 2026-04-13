"""crisis/interface.py — ICrisisUseCase Protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from internal.crisis.type import CrisisInput, CrisisOutput


@runtime_checkable
class ICrisisUseCase(Protocol):
    def assess(self, inp: "CrisisInput") -> "CrisisOutput":
        """Run rule-based crisis assessment from a BIReportBundle."""
        ...


__all__ = ["ICrisisUseCase"]
