"""Reporting module errors."""

from __future__ import annotations


class MartBuildError(Exception):
    """Raised when MartBundle assembly fails."""


class ReportBuildError(Exception):
    """Raised when BIReportBundle construction fails."""


__all__ = ["MartBuildError", "ReportBuildError"]
