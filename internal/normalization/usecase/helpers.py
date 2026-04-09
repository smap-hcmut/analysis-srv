"""Normalization helpers — text normalization + heuristic language identification.

Ported from:
  core-analysis/src/smap/normalization/text.py
  core-analysis/src/smap/providers/lid_heuristic.py

External dependencies removed:
  - smap.canonicalization.alias.normalize_alias  → pass text directly
  - smap.providers.base Protocol classes         → replaced with local dataclasses
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Regex constants
# ---------------------------------------------------------------------------

URL_RE = re.compile(r"https?://\S+")
MENTION_RE = re.compile(r"(?<!\w)@[\w\d_.]+", re.UNICODE)
HASHTAG_RE = re.compile(r"#([\w\d_À-ỹà-ỹ-]+)", re.UNICODE)
EMOJI_RE = re.compile(
    "["
    "\U0001f300-\U0001f5ff"
    "\U0001f600-\U0001f64f"
    "\U0001f680-\U0001f6ff"
    "\U0001f700-\U0001f77f"
    "\U0001f900-\U0001f9ff"
    "\U0001fa70-\U0001faff"
    "]+",
    flags=re.UNICODE,
)
WHITESPACE_RE = re.compile(r"\s+")
REPEATED_ALPHA_RE = re.compile(r"([A-Za-zÀ-ỹà-ỹ])\1{2,}", re.UNICODE)
REPEATED_PUNCT_RE = re.compile(r"([!?.,])\1{1,}")
PUNCT_COMPRESS_RE = re.compile(r"[^\w\s#:/+-]", flags=re.UNICODE)
TOKEN_RE = re.compile(r"[A-Za-zÀ-ỹà-ỹ0-9][A-Za-zÀ-ỹà-ỹ0-9+-]*", flags=re.UNICODE)
_TOKEN_RE_WORD = re.compile(r"[\w']+", flags=re.UNICODE)

# ---------------------------------------------------------------------------
# Stopwords / slang maps
# ---------------------------------------------------------------------------

_VI_STOPWORDS = {
    "ai",
    "anh",
    "bác",
    "ban",
    "bạn",
    "cham",
    "chua",
    "cho",
    "co",
    "của",
    "cua",
    "da",
    "được",
    "giao",
    "khong",
    "không",
    "là",
    "la",
    "mấy",
    "mình",
    "này",
    "nha",
    "nhé",
    "nhanh",
    "nhung",
    "nay",
    "roi",
    "rồi",
    "sao",
    "tang",
    "thu",
    "thế",
    "thì",
    "và",
    "vậy",
    "ve",
    "với",
    "xe",
}
_EN_STOPWORDS = {
    # Original
    "all",
    "and",
    "are",
    "back",
    "battery",
    "beats",
    "but",
    "charging",
    "cleaner",
    "day",
    "design",
    "drop",
    "for",
    "feed",
    "good",
    "issue",
    "is",
    "last",
    "launch",
    "looks",
    "matte",
    "most",
    "my",
    "nice",
    "price",
    "quality",
    "routine",
    "service",
    "slow",
    "soft",
    "still",
    "support",
    "the",
    "than",
    "this",
    "tints",
    "with",
    # Added: common function words
    "a",
    "an",
    "i",
    "it",
    "to",
    "in",
    "of",
    "at",
    "be",
    "by",
    "or",
    "so",
    "no",
    "up",
    "do",
    "if",
    "am",
    "on",
    "he",
    "she",
    "we",
    "you",
    "they",
    "was",
    "can",
    "has",
    "had",
    "will",
    "have",
    "from",
    "its",
    "our",
    "got",
    "get",
    # Added: common content words
    "great",
    "love",
    "best",
    "just",
    "like",
    "ok",
    "very",
    "also",
    "about",
    "been",
    "would",
    "their",
    "what",
    "when",
    "how",
    "only",
    "want",
    "know",
    "use",
    "more",
    "her",
    "him",
    "now",
    "any",
    "some",
    "here",
    "there",
    "then",
    "few",
    "both",
    "other",
    "new",
    "even",
    "much",
    "too",
    "really",
    "buy",
    "bought",
    "highly",
    "recommend",
    "everyone",
    "everything",
    "nothing",
    "something",
    "should",
    "could",
    "each",
    "come",
    "said",
    "that",
    "not",
}
_ID_STOPWORDS = {
    "ada",
    "aja",
    "banget",
    "bagus",
    "dan",
    "dengan",
    "ini",
    "itu",
    "kerja",
    "mau",
    "nya",
    "pabrik",
    "produk",
    "sangat",
    "tidak",
    "untuk",
    "yang",
}
_VI_DIACRITIC_MARKERS = (
    "ăâđêôơưàáạảãầấậẩẫằắặẳẵèéẹẻẽềếệểễìíịỉĩòóọỏõồốộổỗờớợởỡùúụủũừứựửữỳýỵỷỹ"
)
_SOCIAL_SLANG_MAP = {
    "ko": "không",
    "k": "không",
    "hok": "không",
    "dc": "được",
    "đc": "được",
    "vs": "với",
    "sp": "sản phẩm",
    "nv": "nhân viên",
}
_LATIN_ENTITY_ALLOWLIST = {"vf", "vinfast", "byd", "catl"}
_MEANINGFUL_EN_SHORTFORMS = {
    "flashsale",
    "delivery",
    "battery",
    "charging",
    "launch",
    "support",
}

# Heuristic LID: language → hint tokens
_LATIN_LANGUAGE_HINTS: dict[str, set[str]] = {
    "en": {
        # Original
        "and",
        "are",
        "bad",
        "but",
        "charging",
        "for",
        "good",
        "link",
        "not",
        "review",
        "slow",
        "that",
        "the",
        "this",
        "with",
        # Added: common function words
        "a",
        "an",
        "i",
        "it",
        "in",
        "to",
        "of",
        "at",
        "be",
        "by",
        "or",
        "so",
        "no",
        "up",
        "do",
        "if",
        "am",
        "on",
        "he",
        "she",
        "we",
        "you",
        "they",
        "was",
        "can",
        "has",
        "had",
        "will",
        "have",
        "from",
        "its",
        "our",
        "got",
        "get",
        "my",
        # Added: common content words
        "great",
        "nice",
        "love",
        "best",
        "just",
        "like",
        "ok",
        "very",
        "also",
        "about",
        "been",
        "would",
        "their",
        "what",
        "when",
        "how",
        "only",
        "want",
        "know",
        "use",
        "more",
        "her",
        "him",
        "now",
        "any",
        "some",
        "here",
        "there",
        "then",
        "few",
        "both",
        "other",
        "new",
        "even",
        "much",
        "too",
        "these",
        "those",
        "each",
        "come",
        "been",
        "said",
        "should",
        "could",
        "really",
        "buy",
        "bought",
        "highly",
        "recommend",
        "everyone",
        "everything",
        "nothing",
        "something",
        "anyone",
        "someone",
    },
    "vi": {
        "ban",
        "bác",
        "cho",
        "của",
        "cua",
        "đẹp",
        "dep",
        "khong",
        "la",
        "may",
        "nha",
        "nhe",
        "thoi",
        "vay",
        "voi",
        "xe",
        "vậy",
        "nhé",
        "thôi",
        "máy",
        "không",
        "mà",
    },
    "es": {"con", "de", "el", "esta", "muy", "para", "pero", "que", "una", "y"},
    "fr": {"avec", "ce", "dans", "des", "est", "mais", "pas", "pour", "que", "une"},
    "de": {"aber", "das", "dem", "die", "gut", "mit", "nicht", "und"},
    "pt": {"com", "esta", "mais", "muito", "nao", "para", "por", "que", "uma", "voce"},
    "id": {"banget", "dan", "dengan", "ini", "itu", "tidak", "untuk", "yang"},
}
_VI_MARKERS = {"đ", "ă", "â", "ê", "ô", "ơ", "ư"}

# ---------------------------------------------------------------------------
# Internal lightweight types (replace smap.providers.base Protocol classes)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _ProviderProvenance:
    provider_name: str
    provider_version: str
    model_id: str


@dataclass(frozen=True)
class _LanguageResult:
    language: str
    confidence: float
    source: str  # "heuristic" | "explicit"
    provider_provenance: _ProviderProvenance
    metadata: dict


@dataclass(frozen=True)
class TextNormResult:
    """Result of normalize_social_text()."""

    raw_text: str
    normalized_text: str
    normalized_text_compact: str
    urls: list[str]
    hashtags: list[str]
    emojis: list[str]
    language: str
    language_confidence: float
    language_provider: str
    language_provider_version: str
    language_model_id: str
    language_source: str
    language_metadata: dict
    language_supported: bool
    language_rejection_reason: str | None
    text_quality_label: str
    text_quality_flags: list[str]
    text_quality_score: float
    mixed_language_uncertain: bool
    semantic_route_hint: str


# ---------------------------------------------------------------------------
# Basic text utilities
# ---------------------------------------------------------------------------


def normalize_whitespace(text: str) -> str:
    return WHITESPACE_RE.sub(" ", text).strip()


def extract_urls(text: str) -> list[str]:
    return URL_RE.findall(text)


def extract_emojis(text: str) -> list[str]:
    return [match.group(0) for match in EMOJI_RE.finditer(text)]


def normalize_hashtags(
    text: str, explicit_hashtags: list[str] | None = None
) -> list[str]:
    hashtags = [match.lower() for match in HASHTAG_RE.findall(text)]
    if explicit_hashtags:
        hashtags.extend(tag.lower().lstrip("#") for tag in explicit_hashtags if tag)
    deduped: list[str] = []
    for hashtag in hashtags:
        if hashtag not in deduped:
            deduped.append(hashtag)
    return deduped


# ---------------------------------------------------------------------------
# Heuristic Language Identification (ported from lid_heuristic.py)
# ---------------------------------------------------------------------------


def canonicalize_language_label(value: str | None) -> str:
    if value is None:
        return "unknown"
    cleaned = value.strip().lower()
    if cleaned.startswith("__label__"):
        cleaned = cleaned.removeprefix("__label__")
    cleaned = cleaned.replace("_", "-")
    primary = cleaned.split("-", 1)[0]
    if primary == "jp":
        return "ja"
    if primary == "in":
        return "id"
    if re.fullmatch(r"[a-z]{2,3}", primary):
        return primary
    return cleaned or "unknown"


def _detect_script_languages(text: str) -> dict[str, float]:
    counts: Counter[str] = Counter()
    for char in text:
        codepoint = ord(char)
        if 0x3040 <= codepoint <= 0x30FF:
            counts["ja"] += 1
        elif 0x4E00 <= codepoint <= 0x9FFF:
            counts["zh"] += 1
        elif 0xAC00 <= codepoint <= 0xD7AF:
            counts["ko"] += 1
        elif 0x0400 <= codepoint <= 0x04FF:
            counts["ru"] += 1
        elif 0x0600 <= codepoint <= 0x06FF:
            counts["ar"] += 1
        elif 0x0900 <= codepoint <= 0x097F:
            counts["hi"] += 1
        elif 0x0E00 <= codepoint <= 0x0E7F:
            counts["th"] += 1
    total = sum(counts.values())
    if total <= 0:
        return {}
    return {lang: round(count / total, 4) for lang, count in counts.items()}


def _heuristic_language_candidates(text: str) -> dict[str, float]:
    # Note: skip normalize_alias — pass text directly
    # Lowercase tokens so hint matching is case-insensitive (fix: "Great" → "great")
    tokens = [token.lower() for token in _TOKEN_RE_WORD.findall(text) if token]
    if not tokens:
        script_scores = _detect_script_languages(text)
        return script_scores or {"unknown": 0.0}

    scores: dict[str, float] = {}
    token_count = max(len(tokens), 1)
    for language, hints in _LATIN_LANGUAGE_HINTS.items():
        overlap = sum(1 for token in tokens if token in hints)
        if overlap <= 0:
            continue
        coverage = overlap / token_count
        bonus = 0.12 if language == "vi" and any(ord(c) > 127 for c in text) else 0.0
        scores[language] = round(min(coverage + bonus, 0.96), 4)

    for language, score in _detect_script_languages(text).items():
        scores[language] = max(
            scores.get(language, 0.0), round(min(0.55 + (score * 0.4), 0.98), 4)
        )
    if any(marker in text.casefold() for marker in _VI_MARKERS):
        scores["vi"] = max(scores.get("vi", 0.0), 0.52)

    if not scores:
        return {"unknown": 0.0}
    return scores


def _looks_mixed_language(
    text: str,
    candidate_scores: dict[str, float],
    *,
    mixed_confidence_threshold: float,
    mixed_gap_threshold: float,
    script_override_enabled: bool,
) -> bool:
    ranked = sorted(candidate_scores.items(), key=lambda item: (-item[1], item[0]))
    if len(ranked) >= 2:
        top_language, top_score = ranked[0]
        second_language, second_score = ranked[1]
        if top_language != second_language and (
            (
                second_score >= (mixed_confidence_threshold * 0.45)
                and (top_score - second_score) <= mixed_gap_threshold
            )
            or (
                {top_language, second_language} == {"vi", "en"}
                and second_score >= 0.22
                and (top_score - second_score) <= 0.24
            )
        ):
            return True
    if not script_override_enabled:
        return False
    script_scores = _detect_script_languages(text)
    return len(script_scores) >= 2 and max(script_scores.values(), default=0.0) < 0.88


def _heuristic_detect(
    text: str,
    *,
    mixed_confidence_threshold: float = 0.55,
    mixed_gap_threshold: float = 0.12,
    script_override_enabled: bool = True,
) -> _LanguageResult:
    candidates = _heuristic_language_candidates(text)
    filtered = {
        lang: score for lang, score in candidates.items() if lang and lang != "unknown"
    }
    if not filtered:
        language, confidence = "unknown", 0.0
        top_candidates: list[tuple[str, float]] = []
    else:
        ranked = sorted(filtered.items(), key=lambda item: (-item[1], item[0]))
        if _looks_mixed_language(
            text,
            filtered,
            mixed_confidence_threshold=mixed_confidence_threshold,
            mixed_gap_threshold=mixed_gap_threshold,
            script_override_enabled=script_override_enabled,
        ):
            top_score = ranked[0][1]
            second_score = ranked[1][1] if len(ranked) > 1 else top_score
            language = "mixed"
            confidence = round(
                max((top_score + second_score) / 2.0, mixed_confidence_threshold), 4
            )
        else:
            language, confidence = ranked[0][0], ranked[0][1]
        top_candidates = ranked[:3]

    return _LanguageResult(
        language=language,
        confidence=confidence,
        source="heuristic",
        provider_provenance=_ProviderProvenance(
            provider_name="heuristic_lid",
            provider_version="heuristic-lid-v2",
            model_id="heuristic-social-lid",
        ),
        metadata={
            "candidate_count": len(filtered),
            "top_candidates": ", ".join(
                f"{lang}:{score:.3f}" for lang, score in top_candidates
            ),
        },
    )


def _explicit_language_result(explicit_language: str) -> _LanguageResult:
    language = canonicalize_language_label(explicit_language)
    return _LanguageResult(
        language=language,
        confidence=1.0 if language != "unknown" else 0.0,
        source="explicit",
        provider_provenance=_ProviderProvenance(
            provider_name="record_language_hint",
            provider_version="record-language-v2",
            model_id="record-explicit-language",
        ),
        metadata={"raw_explicit_language": explicit_language},
    )


def _resolve_language(text: str, explicit_language: str | None) -> _LanguageResult:
    if explicit_language:
        return _explicit_language_result(explicit_language)
    return _heuristic_detect(text)


# ---------------------------------------------------------------------------
# Processing text helpers
# ---------------------------------------------------------------------------


def _segment_hashtag(hashtag: str) -> str:
    segmented = (
        re.sub(r"([a-z])([A-Z])", r"\1 \2", hashtag).replace("_", " ").replace("-", " ")
    )
    segmented = re.sub(r"([A-Za-z])(\d)", r"\1 \2", segmented)
    segmented = re.sub(r"(\d)([A-Za-z])", r"\1 \2", segmented)
    return normalize_whitespace(segmented)


def _normalize_processing_text(raw_text: str, hashtags: list[str]) -> str:
    normalized = raw_text
    normalized = URL_RE.sub(" ", normalized)
    normalized = MENTION_RE.sub(" ", normalized)
    normalized = EMOJI_RE.sub(" ", normalized)
    for hashtag in hashtags:
        segmented = _segment_hashtag(hashtag)
        if segmented:
            normalized = normalized.replace(f"#{hashtag}", f" {segmented} ")
    normalized = REPEATED_ALPHA_RE.sub(r"\1\1", normalized)
    normalized = REPEATED_PUNCT_RE.sub(r"\1", normalized)
    normalized = normalize_whitespace(normalized)
    for slang, replacement in _SOCIAL_SLANG_MAP.items():
        normalized = re.sub(
            rf"(?<!\w){re.escape(slang)}(?!\w)",
            replacement,
            normalized,
            flags=re.IGNORECASE,
        )
    return normalize_whitespace(normalized)


def _compact_processing_text(normalized_text: str) -> str:
    compact = PUNCT_COMPRESS_RE.sub(" ", normalized_text.casefold())
    compact = compact.replace("/", " ")
    compact = compact.replace("_", " ")
    return normalize_whitespace(compact)


# ---------------------------------------------------------------------------
# Language gate
# ---------------------------------------------------------------------------


def _unsupported_script_score(text: str) -> float:
    unsupported_chars = 0
    total_letters = 0
    for char in text:
        if not char.isalpha():
            continue
        total_letters += 1
        codepoint = ord(char)
        if (
            0x0900 <= codepoint <= 0x097F
            or 0x0E00 <= codepoint <= 0x0E7F
            or 0x0980 <= codepoint <= 0x09FF
            or 0x4E00 <= codepoint <= 0x9FFF
            or 0x3040 <= codepoint <= 0x30FF
            or 0xAC00 <= codepoint <= 0xD7AF
        ):
            unsupported_chars += 1
    if total_letters == 0:
        return 0.0
    return unsupported_chars / total_letters


def _is_entity_like_token(token: str) -> bool:
    if any(c.isdigit() for c in token):
        return True
    if token in _LATIN_ENTITY_ALLOWLIST:
        return True
    return (
        len(token) <= 3
        and token.isascii()
        and token.isalpha()
        and token not in _EN_STOPWORDS
        and token not in _ID_STOPWORDS
    )


def _is_semantic_token(token: str) -> bool:
    if token in _LATIN_ENTITY_ALLOWLIST:
        return False
    if any(c.isdigit() for c in token):
        return False
    if len(token) < 2:
        return False
    return token.isalpha()


def _supports_vi(token: str) -> bool:
    if token in _VI_STOPWORDS:
        return True
    return any(c in _VI_DIACRITIC_MARKERS for c in token)


def _language_gate(
    raw_text: str,
    compact_text: str,
    provider_result: _LanguageResult,
) -> tuple[str, bool, str | None, dict]:
    tokens = [token for token in TOKEN_RE.findall(compact_text) if token]
    if not tokens:
        return (
            "unsupported",
            False,
            "no_semantic_content",
            {"gate_reason": "no_semantic_content"},
        )

    lower_tokens = [token.casefold() for token in tokens]
    token_count = max(len(lower_tokens), 1)
    vi_hits = sum(1 for token in lower_tokens if token in _VI_STOPWORDS)
    en_hits = sum(1 for token in lower_tokens if token in _EN_STOPWORDS)
    id_hits = sum(1 for token in lower_tokens if token in _ID_STOPWORDS)
    latin_entity_like = sum(1 for token in lower_tokens if _is_entity_like_token(token))
    semantic_tokens = [token for token in lower_tokens if _is_semantic_token(token)]
    semantic_token_count = len(semantic_tokens)
    vi_semantic_hits = sum(1 for token in semantic_tokens if _supports_vi(token))
    en_semantic_hits = sum(1 for token in semantic_tokens if token in _EN_STOPWORDS)
    ascii_semantic_hits = sum(
        1
        for token in semantic_tokens
        if token.isascii() and len(token) >= 4 and token not in _ID_STOPWORDS
    )
    vi_score = vi_hits / token_count
    en_score = en_hits / token_count
    id_score = id_hits / token_count
    if any(c in raw_text.casefold() for c in _VI_DIACRITIC_MARKERS):
        vi_score += 0.28
    provider_language = canonicalize_language_label(provider_result.language)
    if provider_language == "vi":
        vi_score += 0.18
    elif provider_language == "en":
        en_score += 0.16
    elif provider_language == "mixed":
        vi_score += 0.08
        en_score += 0.08
    elif provider_language == "id":
        id_score += 0.18
    unsupported_script = _unsupported_script_score(raw_text)
    unsupported_score = id_score + unsupported_script

    metadata: dict = {
        "gate_provider_language": provider_language,
        "vi_score": round(vi_score, 4),
        "en_score": round(en_score, 4),
        "unsupported_score": round(unsupported_score, 4),
        "entity_like_token_count": latin_entity_like,
        "semantic_token_count": semantic_token_count,
        "vi_semantic_hits": vi_semantic_hits,
        "en_semantic_hits": en_semantic_hits,
        "ascii_semantic_hits": ascii_semantic_hits,
    }
    if unsupported_score >= 0.42 and unsupported_score > (vi_score + en_score + 0.08):
        return (
            "unsupported",
            False,
            "unsupported_language",
            {**metadata, "gate_reason": "unsupported_language"},
        )
    if semantic_token_count == 0:
        rejection = (
            "non_vi_en_latin_noise" if latin_entity_like else "no_semantic_content"
        )
        return "unsupported", False, rejection, {**metadata, "gate_reason": rejection}

    mixed_vi_evidence = (
        vi_score >= 0.18
        or vi_semantic_hits >= 2
        or any(c in raw_text.casefold() for c in _VI_DIACRITIC_MARKERS)
    )
    mixed_en_evidence = en_score >= 0.12 or en_semantic_hits >= 1
    if (
        mixed_vi_evidence
        and mixed_en_evidence
        and semantic_token_count >= 2
        and unsupported_score < 0.24
    ):
        return (
            "mixed",
            True,
            None,
            {**metadata, "gate_reason": "accepted_mixed_verified"},
        )
    if (
        vi_semantic_hits >= 1
        and ascii_semantic_hits >= 2
        and semantic_token_count >= 4
        and provider_language in {"en", "mixed", "unknown"}
        and unsupported_score < 0.18
    ):
        return "mixed", True, None, {**metadata, "gate_reason": "accepted_mixed_bridge"}
    if vi_score >= 0.2 or vi_semantic_hits >= 2:
        return "vi", True, None, {**metadata, "gate_reason": "accepted_vi_verified"}
    if (
        (en_score >= 0.2 and semantic_token_count >= 2)
        or (
            semantic_token_count == 1
            and semantic_tokens[0] in _MEANINGFUL_EN_SHORTFORMS
            and provider_language in {"en", "mixed", "unknown"}
        )
    ) and unsupported_score < 0.18:
        return "en", True, None, {**metadata, "gate_reason": "accepted_en_verified"}
    if latin_entity_like / token_count >= 0.5 and (vi_score + en_score) < 0.18:
        return (
            "unsupported",
            False,
            "non_vi_en_latin_noise",
            {**metadata, "gate_reason": "non_vi_en_latin_noise"},
        )
    if (vi_score + en_score) < 0.18 and semantic_token_count <= 2:
        return (
            "unsupported",
            False,
            "low_vi_en_evidence",
            {**metadata, "gate_reason": "low_vi_en_evidence"},
        )
    # ASCII fallback: mostly-ascii semantic content with no VI/ID evidence.
    # Catches English text where stopword coverage is still low after all scoring.
    if (
        ascii_semantic_hits >= 3
        and vi_score < 0.14
        and id_score < 0.10
        and unsupported_score < 0.15
        and provider_language not in {"vi", "id"}
        and semantic_token_count >= 3
    ):
        return (
            "en",
            True,
            None,
            {**metadata, "gate_reason": "accepted_en_ascii_fallback"},
        )
    return (
        "unsupported",
        False,
        "unsupported_language",
        {**metadata, "gate_reason": "unsupported_language"},
    )


# ---------------------------------------------------------------------------
# Quality scoring
# ---------------------------------------------------------------------------


def _text_quality_flags(
    *,
    raw_text: str,
    normalized_text: str,
    compact_text: str,
    urls: list[str],
    emojis: list[str],
    language_supported: bool,
) -> list[str]:
    tokens = [
        token for token in compact_text.split() if token not in {"url", "mention"}
    ]
    flags: list[str] = []
    if not language_supported:
        flags.append("unsupported_language")
    if len(tokens) <= 2 and len(emojis) >= 2:
        flags.append("emoji_dominant")
    if len(tokens) <= 2 and not urls:
        flags.append("low_information")
    if not tokens and raw_text:
        flags.append("reaction_only")
    if len(urls) >= 2 or (urls and len(tokens) <= 3):
        flags.append("url_heavy")
    if len(set(tokens)) <= 2 and len(tokens) >= 4:
        flags.append("template_like")
    if len(tokens) <= 3 and normalized_text.casefold() in {
        "ok",
        "oke",
        "haha",
        "hehe",
        "nice",
    }:
        flags.append("reaction_only")
    if not tokens:
        flags.append("no_semantic_content")
    return sorted(set(flags))


def _text_quality_label(flags: list[str]) -> str:
    if "unsupported_language" in flags:
        return "unsupported_language"
    if "no_semantic_content" in flags:
        return "no_semantic_content"
    if "reaction_only" in flags:
        return "reaction_only"
    if "emoji_dominant" in flags or "low_information" in flags:
        return "low_information"
    if "url_heavy" in flags or "template_like" in flags:
        return "spam_like"
    return "normal"


def _text_quality_score(flags: list[str]) -> float:
    score = 1.0
    penalties = {
        "unsupported_language": 0.9,
        "reaction_only": 0.45,
        "low_information": 0.3,
        "url_heavy": 0.2,
        "template_like": 0.2,
        "emoji_dominant": 0.15,
    }
    for flag in flags:
        score -= penalties.get(flag, 0.0)
    return round(max(score, 0.05), 4)


# ---------------------------------------------------------------------------
# Main public function
# ---------------------------------------------------------------------------


def normalize_social_text(
    text: str,
    explicit_hashtags: list[str] | None,
    explicit_language: str | None,
) -> TextNormResult:
    """Normalize a social media text and return a TextNormResult."""
    raw_text = normalize_whitespace(unicodedata.normalize("NFKC", text))
    urls = extract_urls(raw_text)
    hashtags = normalize_hashtags(raw_text, explicit_hashtags=explicit_hashtags)
    emojis = extract_emojis(raw_text)
    language_result = _resolve_language(raw_text, explicit_language)
    normalized_text = _normalize_processing_text(raw_text, hashtags)
    normalized_text_compact = _compact_processing_text(normalized_text)
    language_label, language_supported, rejection_reason, gate_metadata = (
        _language_gate(
            raw_text,
            normalized_text_compact,
            language_result,
        )
    )
    quality_flags = _text_quality_flags(
        raw_text=raw_text,
        normalized_text=normalized_text,
        compact_text=normalized_text_compact,
        urls=urls,
        emojis=emojis,
        language_supported=language_supported,
    )
    text_quality_label = _text_quality_label(quality_flags)
    text_quality_score = _text_quality_score(quality_flags)
    lang_metadata: dict = {
        **{
            key: value
            for key, value in language_result.metadata.items()
            if isinstance(value, (str, int, float, bool)) or value is None
        },
        **gate_metadata,
    }
    return TextNormResult(
        raw_text=raw_text,
        normalized_text=normalized_text,
        normalized_text_compact=normalized_text_compact,
        urls=urls,
        hashtags=hashtags,
        emojis=emojis,
        language=language_label,
        language_confidence=round(
            max(
                language_result.confidence,
                0.72 if language_label in {"vi", "en", "mixed"} else 0.0,
            ),
            4,
        ),
        language_provider=language_result.provider_provenance.provider_name,
        language_provider_version=language_result.provider_provenance.provider_version,
        language_model_id=language_result.provider_provenance.model_id,
        language_source=language_result.source,
        language_metadata=lang_metadata,
        language_supported=language_supported,
        language_rejection_reason=rejection_reason,
        text_quality_label=text_quality_label,
        text_quality_flags=quality_flags,
        text_quality_score=text_quality_score,
        mixed_language_uncertain=language_label == "mixed",
        semantic_route_hint="semantic_skip"
        if not language_supported
        else "semantic_full",
    )


__all__ = ["normalize_social_text", "TextNormResult", "canonicalize_language_label"]
