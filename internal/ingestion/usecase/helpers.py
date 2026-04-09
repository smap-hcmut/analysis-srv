"""Ingestion helpers — depth detection and root_id derivation from UAPRecord."""

from internal.model.uap import UAPRecord
from ..constant import DOC_TYPE_DEPTH, ROOT_DOC_TYPES


def detect_depth(record: UAPRecord) -> int:
    """Return the hierarchy depth for a UAPRecord.

    Uses ``content.doc_type`` as the primary signal:
    - post / video / news / feedback → 0 (root)
    - comment → 1
    - reply → 2
    Falls back to 0 for unknown types.
    """
    return DOC_TYPE_DEPTH.get(record.content.doc_type, 0)


def derive_root_id(record: UAPRecord, depth_map: dict[str, int]) -> str:
    """Derive root_id for a record.

    Strategy:
    1. If depth == 0, root_id = doc_id (the record IS the root).
    2. Otherwise, follow parent_id upward until we find a depth-0 record in
       `depth_map`, or until parent_id is absent.
    3. If the chain cannot be resolved, fall back to doc_id.
    """
    doc_id = record.content.doc_id
    depth = DOC_TYPE_DEPTH.get(record.content.doc_type, 0)

    if depth == 0:
        return doc_id

    # Attempt to resolve root by following parent chain within the batch.
    # Single-pass: we only have depth_map for the current batch, so we cannot
    # walk further than one hop without risking a dangling reference.
    parent_id = record.content.parent.parent_id
    if parent_id:
        parent_depth = depth_map.get(parent_id)
        if parent_depth is not None and parent_depth == 0:
            return parent_id

    # Fall back: use parent_id if available, else self
    return parent_id or doc_id


__all__ = ["detect_depth", "derive_root_id"]
