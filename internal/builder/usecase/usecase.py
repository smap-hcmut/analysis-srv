from typing import Optional

from pkg.logger.logger import Logger
from ..interface import IResultBuilderUseCase
from ..type import BuildInput, BuildOutput
from .process import process as _process

class ResultBuilderUseCase(IResultBuilderUseCase):
    def __init__(self, logger: Optional[Logger] = None):
        self.logger = logger

    def build(self, input_data: BuildInput) -> BuildOutput:
        return _process(input_data, self.logger)
