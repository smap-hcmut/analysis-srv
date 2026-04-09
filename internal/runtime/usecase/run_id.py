from datetime import datetime, timezone


def default_run_id() -> str:
    """Generate a run_id in the format run-YYYYMMDDTHHMMSSz (UTC).

    Example: "run-20260409T143022Z"
    """
    now = datetime.now(timezone.utc)
    return now.strftime("run-%Y%m%dT%H%M%SZ")


__all__ = ["default_run_id"]
