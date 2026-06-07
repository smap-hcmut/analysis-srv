"""Auto-ontology discovery for unknown / new domains.

Periodically scans post_insight for projects whose domain resolves to
``_default`` (no canonical ontology yet) and writes the top discovered
keywords back to the project's ontology Redis cache so the next consumer
pass scores them as in-domain signals.

The discovered rules are tagged ``auto_generated=True`` so a human
operator can review or override them from the UI before they're trusted
for crisis triggers.
"""

from .updater import AutoOntologyUpdater  # noqa: F401

__all__ = ["AutoOntologyUpdater"]
