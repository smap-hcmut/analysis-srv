from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

from internal.model.uap import UAPRecord
from internal.model.insight_message import InsightMessage

if TYPE_CHECKING:
    from internal.analytics.type import AnalyticsResult


@dataclass
class BuildInput:
    uap_record: UAPRecord
    analytics_result: "AnalyticsResult"


@dataclass
class BuildOutput:
    enriched: InsightMessage
    success: bool = True
    error_message: Optional[str] = None
