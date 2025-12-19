"""Utility modules for Analytics Engine."""

from utils.project_id_extractor import extract_project_id
from utils.uuid_utils import extract_uuid, is_valid_uuid
from utils.id_utils import (
    ensure_string_id,
    is_bigint_id,
    detect_truncated_id,
    validate_tiktok_id,
    validate_post_id,
    log_id_warnings,
)
from utils.json_encoder import (
    BigIntEncoder,
    dumps_safe,
    serialize_analytics_result,
    sanitize_analytics_data,
    sanitize_null_string,
    sanitize_boolean,
)
from utils.debug_logging import (
    should_log_debug,
    log_raw_event_payload,
    log_extracted_item_data,
    log_analytics_payload_before_save,
    log_data_quality_metrics,
)

__all__ = [
    # Project ID
    "extract_project_id",
    # UUID utils
    "extract_uuid",
    "is_valid_uuid",
    # ID utils
    "ensure_string_id",
    "is_bigint_id",
    "detect_truncated_id",
    "validate_tiktok_id",
    "validate_post_id",
    "log_id_warnings",
    # JSON encoder
    "BigIntEncoder",
    "dumps_safe",
    "serialize_analytics_result",
    # Data sanitization
    "sanitize_analytics_data",
    "sanitize_null_string",
    "sanitize_boolean",
    # Debug logging
    "should_log_debug",
    "log_raw_event_payload",
    "log_extracted_item_data",
    "log_analytics_payload_before_save",
    "log_data_quality_metrics",
]
