"""Unit tests for IntentClassifier.

Tests cover:
- Pattern matching for all 7 intent categories
- Priority-based conflict resolution
- Skip logic for SPAM/SEEDING
- Edge cases (empty, None, long text, etc.)
"""

import pytest
from services.analytics.intent import Intent, IntentClassifier, IntentResult


class TestPatternMatching:
    """Test 2.1: Pattern matching for all intent categories."""

    @pytest.fixture
    def classifier(self):
        """Create IntentClassifier instance."""
        return IntentClassifier()

    def test_crisis_pattern_matching(self, classifier):
        """Test CRISIS patterns (tẩy chay, lừa đảo, scam, phốt)."""
        test_cases = [
            "VinFast lừa đảo khách hàng",
            "Tẩy chay sản phẩm này",
            "Đây là scam rõ ràng",
            "Phốt to về công ty",
        ]
        for text in test_cases:
            result = classifier.predict(text)
            assert result.intent == Intent.CRISIS, f"Failed for: {text}"
            assert not result.should_skip, "CRISIS should not be skipped"

    def test_seeding_pattern_matching(self, classifier):
        """Test SEEDING patterns (phone numbers, contact info)."""
        test_cases = [
            "Liên hệ mua xe 0912345678",
            "Inbox zalo 0987654321",
            "Chat shop để biết giá",
            "Inbox mua ngay",
        ]
        for text in test_cases:
            result = classifier.predict(text)
            assert result.intent == Intent.SEEDING, f"Failed for: {text}"
            assert result.should_skip, "SEEDING should be skipped"

    def test_spam_pattern_matching(self, classifier):
        """Test SPAM patterns (vay tiền, bán sim)."""
        test_cases = [
            "Vay tiền lãi suất thấp",
            "Vay vốn nhanh chóng",
            "Bán sim số đẹp",
        ]
        for text in test_cases:
            result = classifier.predict(text)
            assert result.intent == Intent.SPAM, f"Failed for: {text}"
            assert result.should_skip, "SPAM should be skipped"

    def test_complaint_pattern_matching(self, classifier):
        """Test COMPLAINT patterns (phàn nàn, thất vọng)."""
        test_cases = [
            "Xe lỗi mãi không sửa, thất vọng quá",
            "Dịch vụ tệ quá đi",
            "Chất lượng kém, không đáng tiền",
        ]
        for text in test_cases:
            result = classifier.predict(text)
            assert result.intent == Intent.COMPLAINT, f"Failed for: {text}"
            assert not result.should_skip, "COMPLAINT should not be skipped"

    def test_lead_pattern_matching(self, classifier):
        """Test LEAD patterns (hỏi giá, mua xe)."""
        test_cases = [
            "Giá xe bao nhiêu shop?",
            "Mua ở đâu được không?",
            "Test drive được không?",
        ]
        for text in test_cases:
            result = classifier.predict(text)
            assert result.intent == Intent.LEAD, f"Failed for: {text}"
            assert not result.should_skip, "LEAD should not be skipped"

    def test_support_pattern_matching(self, classifier):
        """Test SUPPORT patterns (cách sử dụng, bảo hành)."""
        test_cases = [
            "Cách sạc xe như thế nào?",
            "Showroom ở đâu vậy?",
            "Bảo hành bao lâu?",
        ]
        for text in test_cases:
            result = classifier.predict(text)
            assert result.intent == Intent.SUPPORT, f"Failed for: {text}"
            assert not result.should_skip, "SUPPORT should not be skipped"

    def test_discussion_default(self, classifier):
        """Test DISCUSSION as default when no patterns match."""
        test_cases = [
            "Xe VinFast đẹp nhỉ",
            "Hôm nay trời đẹp",
            "Chúc mọi người cuối tuần vui vẻ",
        ]
        for text in test_cases:
            result = classifier.predict(text)
            assert result.intent == Intent.DISCUSSION, f"Failed for: {text}"
            assert not result.should_skip, "DISCUSSION should not be skipped"

    def test_case_insensitive_matching(self, classifier):
        """Test case-insensitive pattern matching."""
        test_cases = [
            ("LỪA ĐẢO", Intent.CRISIS),
            ("GIÁ XE BAO NHIÊU?", Intent.LEAD),
            ("vay tiền", Intent.SPAM),
            ("Thất Vọng Quá", Intent.COMPLAINT),
        ]
        for text, expected_intent in test_cases:
            result = classifier.predict(text)
            assert result.intent == expected_intent, f"Failed for: {text}"


class TestPriorityResolution:
    """Test 2.2: Priority-based conflict resolution."""

    @pytest.fixture
    def classifier(self):
        """Create IntentClassifier instance."""
        return IntentClassifier()

    def test_crisis_overrides_lead(self, classifier):
        """Test CRISIS (priority 10) overrides LEAD (priority 5)."""
        text = "VinFast lừa đảo, giá bao nhiêu?"
        result = classifier.predict(text)
        assert result.intent == Intent.CRISIS
        assert "lừa" in " ".join(result.matched_patterns).lower()

    def test_seeding_overrides_complaint(self, classifier):
        """Test SEEDING (priority 9) overrides COMPLAINT (priority 7)."""
        text = "Dịch vụ tệ, liên hệ 0912345678"
        result = classifier.predict(text)
        assert result.intent == Intent.SEEDING
        assert result.should_skip

    def test_priority_order_validation(self, classifier):
        """Test complete priority order."""
        # CRISIS (10) > SEEDING (9) > SPAM (9) > COMPLAINT (7) > LEAD (5) > SUPPORT (4) > DISCUSSION (1)
        assert Intent.CRISIS.priority == 10
        assert Intent.SEEDING.priority == 9
        assert Intent.SPAM.priority == 9
        assert Intent.COMPLAINT.priority == 7
        assert Intent.LEAD.priority == 5
        assert Intent.SUPPORT.priority == 4
        assert Intent.DISCUSSION.priority == 1

    def test_multiple_pattern_matches(self, classifier):
        """Test text matching multiple patterns within same intent."""
        text = "VinFast lừa đảo scam khách hàng"  # Multiple CRISIS patterns
        result = classifier.predict(text)
        assert result.intent == Intent.CRISIS
        assert len(result.matched_patterns) >= 2
        assert result.confidence > 0.6  # Higher confidence with multiple matches

    def test_priority_tie_breaking(self, classifier):
        """Test tie-breaking when multiple intents have same priority."""
        # SEEDING and SPAM both have priority 9
        text = "Vay tiền, liên hệ 0912345678"
        result = classifier.predict(text)
        # Should match either SEEDING or SPAM (both valid)
        assert result.intent in [Intent.SEEDING, Intent.SPAM]
        assert result.should_skip  # Both should skip


class TestSkipLogic:
    """Test 2.3: Skip logic for filtering spam."""

    @pytest.fixture
    def classifier(self):
        """Create IntentClassifier instance."""
        return IntentClassifier()

    def test_spam_should_skip(self, classifier):
        """Test SPAM returns should_skip=True."""
        result = classifier.predict("Vay tiền lãi suất 0%")
        assert result.intent == Intent.SPAM
        assert result.should_skip is True

    def test_seeding_should_skip(self, classifier):
        """Test SEEDING returns should_skip=True."""
        result = classifier.predict("Inbox shop 0912345678")
        assert result.intent == Intent.SEEDING
        assert result.should_skip is True

    def test_complaint_should_not_skip(self, classifier):
        """Test COMPLAINT returns should_skip=False."""
        result = classifier.predict("Dịch vụ tệ quá")
        assert result.intent == Intent.COMPLAINT
        assert result.should_skip is False

    def test_lead_should_not_skip(self, classifier):
        """Test LEAD returns should_skip=False."""
        result = classifier.predict("Giá xe bao nhiêu?")
        assert result.intent == Intent.LEAD
        assert result.should_skip is False

    def test_crisis_should_not_skip(self, classifier):
        """Test CRISIS returns should_skip=False."""
        result = classifier.predict("VinFast lừa đảo")
        assert result.intent == Intent.CRISIS
        assert result.should_skip is False


class TestEdgeCases:
    """Test 2.4: Edge cases and error handling."""

    @pytest.fixture
    def classifier(self):
        """Create IntentClassifier instance."""
        return IntentClassifier()

    def test_empty_string_input(self, classifier):
        """Test handling of empty string."""
        result = classifier.predict("")
        assert result.intent == Intent.DISCUSSION
        assert result.confidence == 1.0  # 100% confident it's discussion (no other patterns)
        assert result.matched_patterns == []
        assert not result.should_skip

    def test_none_input(self, classifier):
        """Test handling of None input."""
        result = classifier.predict(None)
        assert result.intent == Intent.DISCUSSION
        assert result.confidence == 1.0  # 100% confident it's discussion (no other patterns)
        assert result.matched_patterns == []
        assert not result.should_skip

    def test_very_long_text(self, classifier):
        """Test handling of very long text (>1000 chars)."""
        long_text = "Xe VinFast " * 200  # ~2400 characters
        result = classifier.predict(long_text)
        assert isinstance(result, IntentResult)
        assert result.intent in Intent

    def test_special_characters(self, classifier):
        """Test handling of special characters."""
        test_cases = [
            "!!!VinFast lừa đảo!!!",
            "Giá xe??? @@@",
            "Xe #VinFast $$$",
        ]
        for text in test_cases:
            result = classifier.predict(text)
            assert isinstance(result, IntentResult)
            # Should still detect patterns despite special chars
            assert result.intent in Intent

    def test_mixed_vietnamese_english(self, classifier):
        """Test handling of mixed Vietnamese and English."""
        test_cases = [
            "VinFast scam customers",
            "How much is the price? Giá bao nhiêu?",
            "Xe lỗi rồi, car has problems",
        ]
        for text in test_cases:
            result = classifier.predict(text)
            assert isinstance(result, IntentResult)
            assert result.intent in Intent


class TestConfidenceCalculation:
    """Additional tests for confidence scoring."""

    @pytest.fixture
    def classifier(self):
        """Create IntentClassifier instance."""
        return IntentClassifier()

    def test_single_match_confidence(self, classifier):
        """Test confidence with single pattern match."""
        result = classifier.predict("Giá xe bao nhiêu?")
        assert 0.5 <= result.confidence <= 0.7

    def test_multiple_match_confidence(self, classifier):
        """Test confidence increases with multiple matches."""
        result = classifier.predict("Lừa đảo scam khách hàng")
        assert result.confidence > 0.6

    def test_no_match_confidence(self, classifier):
        """Test default confidence when no patterns match."""
        result = classifier.predict("Xe đẹp quá")
        assert result.confidence == 1.0  # 100% confident it's discussion when no patterns match


class TestPhase5EdgeCases:
    """Phase 5.2: Additional edge cases from architecture review."""

    @pytest.fixture
    def classifier(self):
        """Create IntentClassifier instance."""
        return IntentClassifier()

    def test_native_ads_seeding(self, classifier):
        """Case A: Native Ads (Seeding trá hình) - subtle marketing disguised as reviews."""
        test_cases = [
            "Trải nghiệm xe rất tuyệt, liên hệ 0912345678 để biết thêm",
            "Review xe VinFast, inbox shop để xem giá",
            "Cảm ơn showroom đã tư vấn nhiệt tình, liên hệ ngay",
        ]
        for text in test_cases:
            result = classifier.predict(text)
            assert result.intent == Intent.SEEDING, f"Failed for: {text}"
            assert result.should_skip is True, "Native ads should be skipped"

    def test_sarcasm_complaint(self, classifier):
        """Case B: Sarcasm (Complaint mỉa mai) - sarcastic complaints."""
        test_cases = [
            "Dịch vụ tuyệt vời quá cơ, gọi 3 ngày không ai bắt máy",
            "Tuyệt vời lắm, xe hỏng mà không ai trả lời điện thoại",
            "Cảm ơn đã làm hỏng xe của tôi, dịch vụ tuyệt vời",
        ]
        for text in test_cases:
            result = classifier.predict(text)
            # Should be COMPLAINT, not DISCUSSION
            assert result.intent == Intent.COMPLAINT, f"Failed for: {text}"
            assert result.should_skip is False, "Complaints should be processed"

    def test_support_vs_lead_distinction(self, classifier):
        """Case C: Support vs Lead - distinguish between support questions and purchase inquiries."""
        support_cases = [
            "Sạc ở đâu?",
            "Cách sạc xe như thế nào?",
            "Trạm sạc gần đây ở đâu?",
        ]
        lead_cases = [
            "Bao tiền?",
            "Giá bao nhiêu?",
            "Gia xe bao nhieu?",  # Unsigned
        ]

        for text in support_cases:
            result = classifier.predict(text)
            assert result.intent == Intent.SUPPORT, f"Support case failed for: {text}"

        for text in lead_cases:
            result = classifier.predict(text)
            assert result.intent == Intent.LEAD, f"Lead case failed for: {text}"

    def test_unsigned_vietnamese_spam(self, classifier):
        """Case D: Unsigned Spam - text without Vietnamese diacritics."""
        test_cases = [
            "vay tien nhanh, lai suat thap",
            "vay von kinh doanh",
            "ban sim so dep",
            "giai ngan trong ngay",
        ]
        for text in test_cases:
            result = classifier.predict(text)
            assert result.intent == Intent.SPAM, f"Failed for: {text}"
            assert result.should_skip is True, "Unsigned spam should be skipped"

    def test_unsigned_vietnamese_crisis(self, classifier):
        """Test unsigned Vietnamese for crisis patterns."""
        test_cases = [
            "VinFast lua dao khach hang",
            "tay chay san pham nay",
            "boc phot cong ty",
        ]
        for text in test_cases:
            result = classifier.predict(text)
            assert result.intent == Intent.CRISIS, f"Failed for: {text}"
            assert result.should_skip is False, "Crisis should not be skipped"

    def test_unsigned_vietnamese_lead(self, classifier):
        """Test unsigned Vietnamese for lead patterns."""
        test_cases = [
            "gia bao nhieu vay?",
            "mua o dau?",
        ]
        for text in test_cases:
            result = classifier.predict(text)
            assert result.intent == Intent.LEAD, f"Failed for: {text}"
