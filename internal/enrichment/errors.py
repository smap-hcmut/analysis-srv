"""Enrichment errors."""

from __future__ import annotations


class EnrichmentError(Exception):
    """Base error for enrichment failures."""


class EnricherUnavailableError(EnrichmentError):
    """Raised when a required enricher is not available."""
