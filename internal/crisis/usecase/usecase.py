"""crisis/usecase/usecase.py — CrisisUseCase."""

from __future__ import annotations

from loguru import logger

from internal.crisis.interface import ICrisisUseCase
from internal.crisis.type import CrisisInput, CrisisOutput
from internal.crisis.usecase.assess_crisis import assess_crisis


class CrisisUseCase(ICrisisUseCase):
    """Rule-based crisis assessment — no external dependencies."""

    def assess(self, inp: CrisisInput) -> CrisisOutput:
        logger.debug(
            "crisis: assessing",
            run_id=inp.run_id,
            project_id=inp.project_id,
        )
        assessment = assess_crisis(
            run_id=inp.run_id,
            project_id=inp.project_id,
            campaign_id=inp.campaign_id,
            reports=inp.bi_reports,
        )
        logger.info(
            "crisis: assessment done",
            run_id=inp.run_id,
            crisis_level=assessment.crisis_level,
            composite_score=assessment.composite_crisis_score,
            signals=len(assessment.signals),
        )
        return CrisisOutput(assessment=assessment)


__all__ = ["CrisisUseCase"]
