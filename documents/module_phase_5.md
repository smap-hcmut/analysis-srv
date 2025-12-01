# PROPOSAL: IMPLEMENT IMPACT & RISK CALCULATOR MODULE

**Module:** 5 (Quantitative Analysis Engine)
**Status:** Ready for Implementation
**Target Files:**

1.  `src/config/impact_config.py` (Configuration)
2.  `src/services/analytics/impact_calculator.py` (Core Logic)
3.  `tests/unit/test_impact.py` (Unit Tests)

## 1\. Mục tiêu (Objectives)

Xây dựng bộ máy tính toán định lượng để chuyển đổi các chỉ số thô (Likes, Views, Sentiment) thành các chỉ số quản trị (Business Metrics):

1.  **Impact Score (0-100):** Đánh giá độ "nóng" của bài viết.
2.  **Risk Level:** Phân loại mức độ nguy hiểm (Low/Medium/High/Critical).
3.  **Entity Classification:** Tự động nhận diện bài viết Viral hoặc bài viết của KOL.

-----

## 2\. Công thức & Logic Toán học (The Math Model)

Chúng ta sử dụng mô hình điểm số tổng hợp (Composite Score Model).

### 2.1. Engagement Score (Sức tương tác)

Mỗi hành động tương tác có trọng số khác nhau (Share \> Save \> Comment \> Like \> View).

$$E_{raw} = (Views \times W_v) + (Likes \times W_l) + (Comments \times W_c) + (Saves \times W_s) + (Shares \times W_{sh})$$

### 2.2. Reach Score (Độ phủ sóng)

Sử dụng thang đo **Logarit cơ số 10** để chuẩn hóa lượng Follower. Điều này giúp ngăn chặn việc các KOL siêu lớn làm lệch hoàn toàn biểu đồ so với người dùng thường.

$$R_{score} = \log_{10}(\text{Followers} + 1)$$

### 2.3. Platform & Sentiment Multiplier (Hệ số điều chỉnh)

  * **Platform:** TikTok dễ viral view hơn Facebook, nên view TikTok cần giảm trọng số (hoặc view FB cần tăng).
  * **Sentiment:** Tin tiêu cực (Negative) lan truyền nhanh và gây hại hơn tin tích cực.

### 2.4. Final Formula (Công thức cuối cùng)

$$RawImpact = E_{raw} \times R_{score} \times M_{platform} \times M_{sentiment}$$

  * **Normalization:** Điểm số cuối cùng sẽ được chuẩn hóa về thang 0-100 bằng hàm `Min-Max Scaling` với trần (Ceiling) định sẵn.

-----

## 3\. Thiết kế Chi tiết (Implementation Details)

### Bước 1: Cấu hình Trọng số (`src/config/impact_config.py`)

```python
class ImpactConfig:
    # 1. Trọng số Tương tác (Interaction Weights)
    WEIGHT_VIEW = 0.01    # View rẻ nhất
    WEIGHT_LIKE = 1.0     # Baseline
    WEIGHT_COMMENT = 2.0  # Nỗ lực cao hơn like
    WEIGHT_SAVE = 3.0     # Tín hiệu quan tâm sâu
    WEIGHT_SHARE = 5.0    # Tín hiệu lan truyền mạnh nhất

    # 2. Hệ số Nền tảng (Platform Multipliers)
    # TikTok dễ viral view ảo -> Hệ số thấp hơn chút hoặc giữ chuẩn
    # Facebook/YouTube view "đắt" hơn
    PLATFORM_WEIGHTS = {
        "TIKTOK": 1.0,
        "FACEBOOK": 1.2,
        "YOUTUBE": 1.5,
        "UNKNOWN": 1.0
    }

    # 3. Hệ số Cảm xúc (Sentiment Amplifiers)
    # Tiêu cực được nhân hệ số cao hơn để cảnh báo rủi ro
    AMP_NEGATIVE = 1.5
    AMP_POSITIVE = 1.1
    AMP_NEUTRAL = 1.0

    # 4. Ngưỡng (Thresholds)
    THRESHOLD_KOL_FOLLOWERS = 50000  # >50k follow là KOL
    THRESHOLD_VIRAL_SCORE = 70       # Điểm Impact > 70 là Viral
    
    # Hằng số chuẩn hóa (Điểm Raw đạt mức này sẽ là 100 điểm)
    # Ví dụ: 1 bài có 10k like, 100k view, KOL 100k follow -> Raw ~ 100,000
    MAX_RAW_SCORE_CEILING = 100000 
```

### Bước 2: Class Logic (`src/services/analytics/impact_calculator.py`)

```python
import math
from typing import Dict, Any
from src.config.impact_config import ImpactConfig

class ImpactCalculator:
    def __init__(self):
        self.cfg = ImpactConfig()

    def calculate(self, 
                  interaction: Dict[str, int], 
                  author: Dict[str, Any], 
                  sentiment_result: Dict[str, Any],
                  platform: str) -> Dict[str, Any]:
        
        # 1. Tính E_raw (Engagement)
        e_score = (
            interaction.get('views', 0) * self.cfg.WEIGHT_VIEW +
            interaction.get('likes', 0) * self.cfg.WEIGHT_LIKE +
            interaction.get('comments', 0) * self.cfg.WEIGHT_COMMENT +
            interaction.get('saves', 0) * self.cfg.WEIGHT_SAVE +
            interaction.get('shares', 0) * self.cfg.WEIGHT_SHARE
        )

        # 2. Tính R_score (Reach - Logarithmic)
        followers = author.get('followers', 0)
        # Cộng 1 để tránh log(0)
        r_score = math.log10(max(1, followers)) 
        
        # Bonus cho tài khoản tích xanh (Verified)
        if author.get('is_verified', False):
            r_score *= 1.2

        # 3. Lấy hệ số điều chỉnh
        # Platform
        plat_multiplier = self.cfg.PLATFORM_WEIGHTS.get(platform.upper(), 1.0)
        
        # Sentiment
        sent_label = sentiment_result.get('label', 'NEUTRAL')
        if sent_label == 'NEGATIVE':
            sent_multiplier = self.cfg.AMP_NEGATIVE
        elif sent_label == 'POSITIVE':
            sent_multiplier = self.cfg.AMP_POSITIVE
        else:
            sent_multiplier = self.cfg.AMP_NEUTRAL

        # 4. Tính Raw Impact
        raw_impact = e_score * r_score * plat_multiplier * sent_multiplier

        # 5. Normalize (0 - 100)
        final_score = min(100.0, (raw_impact / self.cfg.MAX_RAW_SCORE_CEILING) * 100)
        final_score = round(final_score, 2)

        # 6. Phân loại (Classification)
        is_kol = followers >= self.cfg.THRESHOLD_KOL_FOLLOWERS
        is_viral = final_score >= self.cfg.THRESHOLD_VIRAL_SCORE
        
        # 7. Đánh giá Rủi ro (Risk Assessment Matrix)
        risk_level = self._assess_risk(final_score, sent_label, is_kol)

        return {
            "score": final_score,
            "level": risk_level,
            "is_kol": is_kol,
            "is_viral": is_viral,
            "breakdown": {
                "engagement_score": round(e_score, 2),
                "reach_score": round(r_score, 2),
                "raw_impact": round(raw_impact, 2)
            }
        }

    def _assess_risk(self, score: float, label: str, is_kol: bool) -> str:
        """
        Logic Ma trận Rủi ro:
        - CRITICAL: Bài Negative Viral HOẶC KOL chê bai.
        - HIGH: Bài Negative có tương tác khá.
        - MEDIUM: Bài Negative tương tác thấp HOẶC Bài Viral nhưng Neutral.
        - LOW: Bài Positive hoặc ít tương tác.
        """
        if label != 'NEGATIVE':
            return "LOW"

        # Nếu là NEGATIVE:
        if is_kol or score >= 70:
            return "CRITICAL"
        if score >= 40:
            return "HIGH"
        if score >= 10:
            return "MEDIUM"
        
        return "LOW"
```

-----

## 4\. Input & Output Contract

### Input Data

Dữ liệu được lấy từ kết quả của các Module trước.

```python
interaction = {"views": 50000, "likes": 2000, "shares": 500}
author = {"followers": 100000, "is_verified": True}
sentiment = {"label": "NEGATIVE", "score": -0.9}
platform = "TIKTOK"
```

### Output Data

Kết quả trả về để lưu vào DB.

```python
{
    "score": 85.5,        # Rất cao
    "level": "CRITICAL",  # Báo động đỏ
    "is_kol": True,       # Do follower > 50k
    "is_viral": True,     # Do score > 70
    "breakdown": { ... }
}
```

-----

## 5\. Kế hoạch Kiểm thử (Test Plan)

Yêu cầu Agent viết Unit Test (`tests/unit/test_impact.py`) phủ các kịch bản sau:

1.  **Scenario: The "Crisis" (Khủng hoảng)**
      * Input: KOL (100k follow), Negative Sentiment, Share cao.
      * Expect: `score > 80`, `level = CRITICAL`.
2.  **Scenario: The "Silent User" (Người dùng ẩn dật)**
      * Input: User (10 follow), Negative, 0 like/share.
      * Expect: `score < 10`, `level = LOW` (hoặc MEDIUM thấp).
3.  **Scenario: The "Brand Love" (Viral Tích cực)**
      * Input: Viral Post, Positive Sentiment.
      * Expect: `score > 80`, `level = LOW` (Vì tích cực thì không có rủi ro).

-----

### HƯỚNG DẪN HÀNH ĐỘNG CHO AGENT

1.  Tạo file config trước.
2.  Implement class `ImpactCalculator` với logic normalization.
3.  Viết hàm `_assess_risk` cẩn thận vì đây là logic quan trọng nhất để bắn Alert.
4.  Chạy test case để đảm bảo công thức không trả về số âm hoặc số \> 100.
