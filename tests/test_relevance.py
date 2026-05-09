from internal.model.uap import UAPContent, UAPRecord
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
