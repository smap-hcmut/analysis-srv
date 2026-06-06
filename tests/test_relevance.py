from internal.analytics.type import AnalyticsResult
from internal.model.uap import UAPContent, UAPContext, UAPRecord
from internal.relevance import calculate_business_relevance


def _uap(text: str) -> UAPRecord:
    return UAPRecord(content=UAPContent(text=text))


def test_cod_gaming_noise_is_not_treated_as_cash_on_delivery():
    score, reasons = calculate_business_relevance(
        _uap("cod movement is so easy try apex movement buddy")
    )

    assert score < 0.45
    assert "offtopic_cod_gaming" in reasons


def test_cod_mobile_without_logistics_context_is_noise():
    score, reasons = calculate_business_relevance(
        _uap("Cod Mobile is so unserious")
    )

    assert score < 0.45
    assert "offtopic_cod_gaming" in reasons


def test_cash_on_delivery_logistics_remains_relevant():
    score, reasons = calculate_business_relevance(
        _uap("Shop ship COD bi khach bom hang, can thu ho va hoan ung nhanh hon")
    )

    assert score >= 0.28
    assert "logistics_signal" in reasons


def test_grabe_foreign_word_does_not_match_grab_competitor():
    score, reasons = calculate_business_relevance(
        _uap("grabe sayo ko palang nakita joy stick nasa taas")
    )

    assert score < 0.45
    assert "competitor_logistics_comparison" not in reasons


def test_domain_keyword_direct_text_is_relevant_for_non_logistics_domain():
    uap = UAPRecord(
        content=UAPContent(text="Kotex Anh Trai Good Night co concept rat bat mat"),
        context=UAPContext(keywords_matched=["kotex anh trai good night"]),
    )

    score, reasons = calculate_business_relevance(uap)

    assert score >= 0.45
    assert "domain_keyword_mentioned" in reasons


def test_domain_keyword_parent_context_can_index_substantive_comment():
    uap = UAPRecord(
        content=UAPContent(
            doc_type="comment",
            text="Minh thay concept nay hay va co cam xuc hon cac campaign cu",
        ),
        context=UAPContext(keywords_matched=["kotex anh trai good night"]),
    )
    result = AnalyticsResult(
        id="doc-1",
        primary_intent="DISCUSSION",
        aspects_breakdown={"aspects": [{"aspect": "creative_hook"}]},
    )

    score, reasons = calculate_business_relevance(uap, result=result)

    assert score >= 0.45
    assert "domain_keyword_in_context" in reasons
    assert "comment_relevant_by_parent_only" in reasons
