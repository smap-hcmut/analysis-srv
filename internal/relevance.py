"""Business relevance scoring helpers.

The quality score answers "is this text useful?", while business relevance
answers "is this text useful for this campaign/domain?".  Keeping them separate
lets the UI show readable-but-offtopic content without letting it pollute RAG.
"""

from __future__ import annotations

import re
from typing import Any

from internal.model.uap import UAPRecord


MIN_DIRECT_TEXT_LENGTH = 20
PLATFORM_YOUTUBE = "YOUTUBE"
MIN_DYNAMIC_TERM_LENGTH = 5

BRAND_TERMS = (
    "ahamove",
    "aha move",
    "ahatruck",
    "aha truck",
    "ahamart",
    "aha mart",
    "tài xế aha",
    "tai xe aha",
)

LOGISTICS_TERMS = (
    "giao hàng",
    "giao hang",
    "vận chuyển",
    "van chuyen",
    "ship",
    "shipper",
    "tài xế",
    "tai xe",
    "đơn hàng",
    "don hang",
    "cod",
    "thu hộ",
    "thu ho",
    "phí giao",
    "phi giao",
    "cước",
    "cuoc",
    "xe tải",
    "xe tai",
    "xe van",
    "siêu tốc",
    "sieu toc",
    "2h",
    "4h",
    "hủy đơn",
    "huy don",
    "khách bom",
    "khach bom",
    "bom hàng",
    "bom hang",
    "ứng tiền",
    "ung tien",
    "tiền ứng",
    "tien ung",
    "hoàn ứng",
    "hoan ung",
    "rút tiền",
    "rut tien",
    "ví tài xế",
    "vi tai xe",
    "nhận đơn",
    "nhan don",
    "tự động nhận đơn",
    "tu dong nhan don",
    "nổ cuốc",
    "no cuoc",
    "cuốc xe",
    "cuoc xe",
    "chuyến xe",
    "chuyen xe",
    "bị khóa",
    "bi khoa",
    "khóa tài khoản",
    "khoa tai khoan",
    "khóa app",
    "khoa app",
    "khóa ví",
    "khoa vi",
    "tổng đài",
    "tong dai",
    "hỗ trợ",
    "ho tro",
    "ứng dụng",
    "ung dung",
    "tài khoản",
    "tai khoan",
    "đăng ký",
    "dang ky",
)

COD_LOGISTICS_CONTEXT_TERMS = (
    "ship cod",
    "cod giao hang",
    "thu ho",
    "thu hộ",
    "don hang",
    "đơn hàng",
    "giao hang",
    "giao hàng",
    "shipper",
    "khach bom",
    "khách bom",
    "bom hang",
    "bom hàng",
    "thu tien",
    "thu tiền",
    "nhan tien",
    "nhận tiền",
    "ung tien",
    "ứng tiền",
    "delivery",
    "cash on delivery",
    "collect on delivery",
)

COD_GAMING_MARKERS = (
    "codm",
    "call of duty",
    "free fire",
    "apex movement",
    "cod movement",
    "warzone",
    "kill",
    "emot",
    "joystick",
    "joy stick",
    "juego",
    "graficos",
    "gráficos",
    "fps",
    "jugador",
    "jugadores",
    "gameplay",
    "rank",
    "headshot",
    "buddy",
)

COMPETITOR_TERMS = (
    "lalamove",
    "grab",
    "grabexpress",
    "be delivery",
    "shopee express",
    "shopeefood",
    "shopee food",
    "grabfood",
    "grab food",
    "grab bike",
    "grabbike",
    "bike plus",
    "befood",
    "be food",
    "ghn",
    "ghtk",
    "giao hàng nhanh",
    "giao hang nhanh",
    "giao hàng tiết kiệm",
    "giao hang tiet kiem",
    "viettel post",
    "vnpost",
)

GENERIC_SHORT_TERMS = (
    "great job",
    "so nice",
    "very nice",
    "beautiful",
    "hay quá",
    "hay qua",
    "xin giá",
    "xin gia",
    "bao nhiêu",
    "bao nhieu",
    "mua ở đâu",
    "mua o dau",
)

OFFTOPIC_FOREIGN_MARKERS = (
    "nainital",
    "uttarakhand",
    "uttrakhand",
    "himachal",
    "kahani",
    "bhai",
    "samurai",
    "thưởng thức video và nhạc",
    "tải nội dung do bạn sáng tạo",
    "enjoy the videos and music you love",
    "upload original content",
)


def calculate_business_relevance(
    uap: UAPRecord,
    result: Any | None = None,
    text: str | None = None,
) -> tuple[float, list[str]]:
    """Return a 0..1 score and compact human-readable reasons."""
    content_text = _norm(text or (uap.content.text if uap and uap.content else ""))
    context_text = _norm(build_context_summary(uap))
    combined = f"{content_text} {context_text}".strip()
    reasons: list[str] = []
    score = 0.0

    brand_direct = _contains_any(content_text, BRAND_TERMS)
    brand_context = _contains_any(context_text, BRAND_TERMS)
    logistics_direct = _contains_any(content_text, LOGISTICS_TERMS)
    logistics_context = _contains_any(context_text, LOGISTICS_TERMS)
    competitor_direct = _contains_any(content_text, COMPETITOR_TERMS)
    competitor_context = _contains_any(context_text, COMPETITOR_TERMS)
    domain_terms = _domain_terms(uap)
    domain_direct = _contains_any(content_text, domain_terms)
    domain_context = _contains_any(context_text, domain_terms)

    if _looks_cod_gaming(content_text) and not brand_direct:
        return 0.08, ["offtopic_cod_gaming"]

    if brand_direct:
        score += 0.50
        reasons.append("brand_mentioned")
    elif brand_context:
        score += 0.22
        reasons.append("brand_in_parent_context")

    if logistics_direct:
        score += 0.28
        reasons.append("logistics_signal")
    elif logistics_context:
        score += 0.10
        reasons.append("logistics_in_parent_context")

    if competitor_direct and (logistics_direct or logistics_context or brand_context):
        score += 0.16
        reasons.append("competitor_logistics_comparison")
    elif competitor_context and brand_context:
        score += 0.06
        reasons.append("competitor_in_context")

    if domain_direct:
        score += 0.46
        reasons.append("domain_keyword_mentioned")
    elif domain_context:
        # Being on the brand's parent page is a hint, not a guarantee.
        # Lifestyle / spam / unrelated comments on Ahamove fan pages were
        # scoring 0.40 here and clearing the 0.30 ingest gate even though
        # the comment body had nothing to do with the brand. Drop the
        # weight so context-only posts must combine with another signal
        # (intent, aspect, logistics) to clear the gate.
        score += 0.18
        reasons.append("domain_keyword_in_context")

    if result is not None:
        intent = str(getattr(result, "primary_intent", "") or "").upper()
        if intent in {"COMPLAINT", "CRISIS", "SUPPORT", "LEAD"}:
            score += 0.10
            reasons.append(f"intent_{intent.lower()}")

        risk_level = str(getattr(result, "risk_level", "") or "").upper()
        sentiment = str(getattr(result, "overall_sentiment", "") or "").upper()
        if risk_level in {"MEDIUM", "HIGH", "CRITICAL"} and (brand_direct or logistics_direct):
            score += 0.08
            reasons.append(f"risk_{risk_level.lower()}")
        if sentiment == "NEGATIVE" and (brand_direct or logistics_direct or competitor_direct):
            score += 0.05
            reasons.append("negative_business_signal")

        aspects = getattr(result, "aspects_breakdown", {}) or {}
        if (
            isinstance(aspects, dict)
            and aspects.get("aspects")
            and (brand_direct or logistics_direct or brand_context)
        ):
            score += 0.08
            reasons.append("business_aspect_detected")
        elif (
            isinstance(aspects, dict)
            and aspects.get("aspects")
            and (domain_direct or domain_context)
        ):
            score += 0.06
            reasons.append("domain_aspect_detected")

    if len(content_text) >= 80 and (brand_direct or logistics_direct or domain_direct):
        score += 0.06
        reasons.append("substantive_direct_text")

    doc_type = (uap.content.doc_type or "").lower() if uap and uap.content else ""
    direct_business_signal = (
        brand_direct or logistics_direct or competitor_direct or domain_direct
    )
    context_business_signal = (
        brand_context or logistics_context or competitor_context or domain_context
    )

    if doc_type == "comment" and not direct_business_signal:
        if context_business_signal and len(content_text) >= MIN_DIRECT_TEXT_LENGTH:
            score = min(score, 0.48)
            reasons.append("comment_relevant_by_parent_only")
        else:
            score = min(score, 0.18)
            reasons.append("comment_without_business_signal")

    if _is_generic_short(content_text) and not direct_business_signal:
        score = min(score, 0.16)
        reasons.append("generic_short_comment")

    if _looks_offtopic_foreign(content_text) and not direct_business_signal:
        score = min(score, 0.12)
        reasons.append("offtopic_foreign_marker")

    if not combined:
        return 0.0, ["empty_text"]

    return round(_clamp(score), 4), _dedupe(reasons)[:6]


def build_context_summary(uap: UAPRecord) -> str:
    if not uap:
        return ""

    raw = uap.raw or {}
    platform_meta = raw.get("platform_meta") or {}
    youtube_meta = platform_meta.get("youtube") if isinstance(platform_meta, dict) else {}
    if not isinstance(youtube_meta, dict):
        youtube_meta = {}

    parts: list[str] = []
    _append(parts, raw.get("content_title"), "Title")
    _append(parts, raw.get("content_subtitle"), "Subtitle")
    _append(
        parts,
        raw.get("crawl_keyword") or _first(uap.context.keywords_matched),
        "Crawl keyword",
    )
    _append(parts, youtube_meta.get("parent_title"), "Parent video")
    _append(parts, youtube_meta.get("parent_channel_name"), "Parent channel")
    _append(parts, youtube_meta.get("parent_description_snippet"), "Parent description")

    parent_keywords = youtube_meta.get("parent_keywords")
    if isinstance(parent_keywords, list):
        keywords = ", ".join(
            str(item).strip() for item in parent_keywords if str(item).strip()
        )
        _append(parts, keywords, "Parent keywords")

    if (
        uap.ingest
        and uap.ingest.source
        and uap.ingest.source.source_type == PLATFORM_YOUTUBE
    ):
        _append(parts, youtube_meta.get("parent_url"), "Parent url")

    return " | ".join(parts)


def has_direct_business_signal(text: str) -> bool:
    lowered = _norm(text)
    return (
        _contains_any(lowered, BRAND_TERMS)
        or _contains_any(lowered, LOGISTICS_TERMS)
        or _contains_any(lowered, COMPETITOR_TERMS)
    )


def _domain_terms(uap: UAPRecord) -> tuple[str, ...]:
    if not uap:
        return ()

    values: list[Any] = []
    if uap.ingest and uap.ingest.entity:
        values.extend(
            [
                uap.ingest.entity.brand,
                uap.ingest.entity.entity_name,
                uap.ingest.entity.entity_type,
            ]
        )
    if uap.context:
        values.extend(uap.context.keywords_matched or [])

    raw = uap.raw or {}
    # NOTE: do NOT add raw.get("crawl_keyword") here. build_context_summary
    # already includes the crawl keyword in context_text, so adding it to
    # domain_terms creates a guaranteed match (domain_context = True for
    # every keyword-crawled post) and inflates business_relevance_score by
    # +0.40. The 2026-06-09 "Choose Happiness" false-positive — an
    # unrelated FB lifestyle post that scored 0.62 in the Ahamove campaign
    # because it was pulled by the "AhaTruck" keyword — was this loop.
    # domain_type_code stays because it names the brand / vertical and is
    # not directly embedded in context_summary.
    values.extend(
        [
            raw.get("domain_type_code"),
        ]
    )
    content_keywords = raw.get("content_keywords")
    if isinstance(content_keywords, list):
        values.extend(content_keywords)

    terms: list[str] = []
    for value in values:
        _extend_domain_terms(terms, value)

    return tuple(_dedupe(terms))


def _extend_domain_terms(terms: list[str], value: Any) -> None:
    text = _norm(str(value or ""))
    if not text:
        return
    terms.append(text)
    for token in re.split(r"[^0-9a-zÀ-ỹ]+", text, flags=re.IGNORECASE):
        token = token.strip()
        if len(token) >= MIN_DYNAMIC_TERM_LENGTH:
            terms.append(token)


def _append(parts: list[str], value: Any, label: str) -> None:
    if value is None:
        return
    text = str(value).strip()
    if text:
        parts.append(f"{label}: {text[:220]}")


def _first(values: list[str] | None) -> str:
    if not values:
        return ""
    return str(values[0] or "").strip()


def _norm(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "").lower()).strip()


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(_contains_term(text, term) for term in terms)


def _contains_term(text: str, term: str) -> bool:
    if not term:
        return False
    # Avoid short ASCII aliases matching inside unrelated foreign words, e.g.
    # "grab" inside Tagalog "grabe" or "cod" inside "codm".
    if re.fullmatch(r"[a-z0-9][a-z0-9 ]*[a-z0-9]", term):
        return bool(
            re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text)
        )
    return term in text


def _is_generic_short(text: str) -> bool:
    if not text:
        return True
    word_count = len(re.findall(r"[\wÀ-ỹ]+", text, flags=re.UNICODE))
    if word_count <= 4:
        return True
    return len(text) < 45 and _contains_any(text, GENERIC_SHORT_TERMS)


def _looks_offtopic_foreign(text: str) -> bool:
    if not text:
        return False
    if _contains_any(text, OFFTOPIC_FOREIGN_MARKERS):
        return True
    has_vietnamese = _has_vietnamese(text)
    latin_words = re.findall(r"[a-z]{3,}", text)
    if has_vietnamese or not latin_words:
        return False
    common_foreign = {"bhai", "kahani", "hai", "nahi", "story", "part", "please"}
    hits = sum(1 for word in latin_words if word in common_foreign)
    return hits >= 2


def _looks_cod_gaming(text: str) -> bool:
    if not text:
        return False
    if not re.search(r"\bcodm|\bcod\b", text):
        return False
    if _contains_any(text, COD_LOGISTICS_CONTEXT_TERMS):
        return False
    return _contains_any(text, COD_GAMING_MARKERS) or not _has_vietnamese(text)


def _has_vietnamese(text: str) -> bool:
    return bool(
        re.search(
            r"[ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]",
            text,
            re.IGNORECASE,
        )
    )


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
