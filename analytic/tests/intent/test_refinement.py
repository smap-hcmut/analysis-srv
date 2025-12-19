import pytest
from services.analytics.intent.intent_classifier import IntentClassifier, Intent


class TestIntentRefinement:
    @pytest.fixture
    def classifier(self):
        return IntentClassifier()

    def test_case_a_native_ads(self, classifier):
        """Test Case A: Seeding trá hình (Native Ads)"""
        text = "Trải nghiệm chuyến đi Đà Lạt cùng VF8 tuyệt vời. Cảm ơn showroom XYZ đã hỗ trợ nhiệt tình. Liên hệ 0912345678 để nhận ưu đãi."
        result = classifier.predict(text)

        # Should be SEEDING because of phone number and contact info
        assert result.intent == Intent.SEEDING
        assert result.should_skip is True

    def test_case_b_sarcasm(self, classifier):
        """Test Case B: Complaint mỉa mai (Sarcasm)"""
        text = "Dịch vụ VinFast tuyệt vời quá cơ, gọi tổng đài 3 ngày không ai bắt máy."
        result = classifier.predict(text)

        # Should be COMPLAINT despite "tuyệt vời" because of "không ai bắt máy"
        # Note: This relies on the new pattern: "tuyệt\\s*vời.*không.*(bắt\\s*máy|trả\\s*lời)"
        assert result.intent == Intent.COMPLAINT
        assert result.should_skip is False

    def test_case_c_support_vs_lead(self, classifier):
        """Test Case C: Support vs Lead distinction"""

        # Case 1: Support (asking for charging location)
        text_support = "Con này sạc ở đâu vậy ae?"
        result_support = classifier.predict(text_support)
        assert result_support.intent == Intent.SUPPORT

        # Case 2: Lead (asking for price)
        text_lead = "Con này bao tiền?"
        result_lead = classifier.predict(text_lead)
        assert result_lead.intent == Intent.LEAD

    def test_case_d_unsigned_spam(self, classifier):
        """Test Case D: Spam không dấu (Unsigned Spam)"""
        text = "vay tien nhanh lai suat thap lien he zalo"
        result = classifier.predict(text)

        # Should be SPAM/SEEDING
        # Note: "vay tien" is SPAM, "zalo" is SEEDING. Both are skip=True.
        # Priority: SEEDING(9) vs SPAM(8/9).
        # In our implementation SPAM has priority 9 via property, same as SEEDING.
        # So either is fine as long as should_skip is True.
        assert result.should_skip is True
        assert result.intent in [Intent.SPAM, Intent.SEEDING]

    def test_config_loading(self, classifier):
        """Verify that patterns are loaded from config"""
        # We can check if a specific pattern from YAML exists in the compiled patterns
        # For example, "tay chay" (unsigned crisis)

        crisis_patterns = classifier.patterns[Intent.CRISIS]
        # Check if any pattern matches "tay chay"
        matched = False
        for pat in crisis_patterns:
            if pat.search("tay chay"):
                matched = True
                break

        assert matched, "Should match 'tay chay' from external config"
