from typing import Optional

from pkg.logger.logger import Logger
from pkg.spacy_yake.spacy_yake import SpacyYake
from internal.keyword_extraction.interface import IKeywordExtractionUseCase
from internal.keyword_extraction.type import Config, Input, Output, Aspect
from .helpers import load_aspects, build_lookup_map
from .process import process as _process


class KeywordExtractionUseCase(IKeywordExtractionUseCase):
    def __init__(
        self,
        config: Config,
        ai_extractor: SpacyYake,
        logger: Optional[Logger] = None,
    ):
        self.config = config
        self.ai_extractor = ai_extractor
        self.logger = logger

        # Load aspect dictionary and build lookup map
        self.aspect_dict: dict[Aspect, dict[str, list[str]]] = load_aspects(
            config, logger
        )
        self.keyword_map: dict[str, Aspect] = build_lookup_map(self.aspect_dict, logger)

    def process(self, input_data: Input) -> Output:
        return _process(
            input_data=input_data,
            config=self.config,
            aspect_dict=self.aspect_dict,
            keyword_map=self.keyword_map,
            ai_extractor=self.ai_extractor,
            logger=self.logger,
        )
