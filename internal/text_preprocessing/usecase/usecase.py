import re
from typing import Optional

from pkg.logger.logger import Logger
from internal.text_preprocessing.interface import ITextPreprocessingUseCase
from internal.text_preprocessing.type import *
from internal.text_preprocessing.constant import *
from .process import process


class TextPreprocessingUseCase(ITextPreprocessingUseCase):
    def __init__(self, config: Config, logger: Optional[Logger] = None):
        self.config = config
        self.logger = logger

        self.url_pattern = re.compile(PATTERN_URL)
        self.emoji_pattern = re.compile(PATTERN_EMOJI, flags=re.UNICODE)
        self.hashtag_pattern = re.compile(PATTERN_HASHTAG)
        self.whitespace_pattern = re.compile(PATTERN_WHITESPACE)
        self.phone_pattern = re.compile(PATTERN_PHONE_VN)

    def process(self, input_data: Input) -> Output:
        return process(
            input_data=input_data,
            config_min_text_length=self.config.min_text_length,
            config_max_comments=self.config.max_comments,
            url_pattern=self.url_pattern,
            emoji_pattern=self.emoji_pattern,
            hashtag_pattern=self.hashtag_pattern,
            whitespace_pattern=self.whitespace_pattern,
            phone_pattern=self.phone_pattern,
            logger=self.logger,
        )
