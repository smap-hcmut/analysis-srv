from internal.http.analytics_service import public_sentiment_label


def test_public_sentiment_label_prefers_persisted_label_over_signed_score():
    assert public_sentiment_label("POSITIVE", 0.5) == "positive"
    assert public_sentiment_label("NEUTRAL", 0.0) == "neutral"
    assert public_sentiment_label("NEGATIVE", -0.5) == "negative"


def test_public_sentiment_label_fallback_handles_signed_scores():
    assert public_sentiment_label("", 0.5) == "positive"
    assert public_sentiment_label(None, 0.0) == "neutral"
    assert public_sentiment_label("", -0.5) == "negative"
