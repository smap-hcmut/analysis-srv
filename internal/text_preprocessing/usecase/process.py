from typing import Pattern, Optional

from pkg.logger.logger import Logger
from internal.text_preprocessing.type import Input, Output, SourceBreakdown
from internal.text_preprocessing.constant import *
from .helpers import merge_content, normalize, calculate_stats, detect_spam


def process(
    input_data: Input,
    config_min_text_length: int,
    config_max_comments: int,
    url_pattern: Pattern,
    emoji_pattern: Pattern,
    hashtag_pattern: Pattern,
    whitespace_pattern: Pattern,
    phone_pattern: Pattern,
    logger: Optional[Logger] = None,
) -> Output:
    try:
        caption = input_data.content.text
        transcription = input_data.content.transcription
        comments = input_data.comments

        logger.info(
            "internal.text_preprocessing.usecase.process.process: Processing started",
            extra={
                "caption_len": len(caption),
                "transcription_len": len(transcription),
                "comments_count": len(comments),
                "min_text_length": config_min_text_length,
                "max_comments": config_max_comments,
            },
        )

        caption_len = len(caption)
        transcript_len = len(transcription)
        comments_len = sum(len(c.text) for c in comments[:config_max_comments])

        merged_text = merge_content(
            caption=caption,
            comments=comments,
            transcription=transcription,
            max_comments=config_max_comments,
        )

        clean_text = normalize(
            text=merged_text,
            url_pattern=url_pattern,
            emoji_pattern=emoji_pattern,
            hashtag_pattern=hashtag_pattern,
            whitespace_pattern=whitespace_pattern,
            logger=logger,
        )

        has_transcription = bool(transcription and transcription.strip())
        stats = calculate_stats(
            original_text=merged_text,
            clean_text=clean_text,
            has_transcription=has_transcription,
            min_text_length=config_min_text_length,
            hashtag_pattern=hashtag_pattern,
            phone_pattern=phone_pattern,
            logger=logger,
        )

        source_breakdown = SourceBreakdown(
            caption_len=caption_len,
            transcript_len=transcript_len,
            comments_len=comments_len,
        )

        logger.info(
            "internal.text_preprocessing.usecase.process.process: Processing completed",
            extra={
                "clean_text_len": stats.total_length,
                "is_too_short": stats.is_too_short,
                "has_spam": stats.has_phone or stats.has_spam_keyword,
                "hashtag_ratio": stats.hashtag_ratio,
                "reduction_ratio": stats.reduction_ratio,
            },
        )

        is_spam, spam_reasons = detect_spam(clean_text, logger)

        return Output(
            clean_text=clean_text,
            stats=stats,
            source_breakdown=source_breakdown,
            is_spam=is_spam,
            spam_reasons=spam_reasons,
        )

    except ValueError:
        raise
    except Exception as e:
        logger.error("internal.text_preprocessing.usecase.process.process: Processing failed: %s", e)
        raise
