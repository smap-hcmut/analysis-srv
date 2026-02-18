from internal.model.uap import UAPRecord
from internal.analytics.type import Input


def to_pipeline_input(
    uap_record: UAPRecord,
    project_id: str,
) -> Input:
    if not project_id:
        raise ValueError("project_id is required")

    if not uap_record.ingest:
        raise ValueError("uap_record.ingest is required")

    if not uap_record.content:
        raise ValueError("uap_record.content is required")

    return Input(
        uap_record=uap_record,
        project_id=project_id,
    )


__all__ = [
    "to_pipeline_input",
]
