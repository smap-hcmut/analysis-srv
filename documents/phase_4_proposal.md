# PROPOSAL: IMPLEMENT ASPECT-BASED SENTIMENT ANALYZER (ABSA)

**Module:** 4 (Core Intelligence)
**Status:** Ready for Implementation
**Target Files:** `src/services/analytics/sentiment_analyzer.py`, `src/config/sentiment.yaml`

## 1\. Mục tiêu (Objectives)

Xây dựng bộ phân tích cảm xúc đa chiều sử dụng model **PhoBERT ONNX** (đã có) kết hợp với thuật toán **Context Windowing**.

  * **Input:** `clean_text` và danh sách `keywords` (có vị trí `start/end`).
  * **Output:** Điểm số cảm xúc cho toàn bài (Overall) VÀ điểm số cho từng khía cạnh (Aspects).

-----

## 2\. Thuật toán Cốt lõi (Core Algorithms)

### 2.1. Logic Cắt Ngữ Cảnh (Dynamic Context Windowing)

Model Sentiment thường học tốt nhất ở mức độ câu hoặc đoạn ngắn. Nếu đưa cả bài dài, các ý khen/chê sẽ triệt tiêu nhau.
Giải pháp là cắt một "Cửa sổ" (Window) xung quanh từ khóa.

**Quy tắc Cắt:**

1.  **Anchor:** Lấy vị trí của Keyword làm tâm.
2.  **Radius:** Mở rộng sang trái và phải $N$ ký tự (ví dụ: ±60 chars).
3.  **Boundary Snapping (Quan trọng):** Không cắt giữa chừng từ. Phải mở rộng cửa sổ ra đến **khoảng trắng** hoặc **dấu câu** gần nhất để đảm bảo câu có nghĩa.

**Ví dụ:**

  * *Text:* "...xe chạy rất êm ái nhưng **giá** hơi cao so với phân khúc..."
  * *Keyword:* "giá"
  * *Raw Window (±10):* " ái nhưng **giá** hơi cao s" (Vô nghĩa)
  * *Smart Window:* "nhưng **giá** hơi cao so với phân khúc" (Có nghĩa -\> Model hiểu là Negative).

### 2.2. Logic Gộp Điểm (Weighted Aggregation)

Một Aspect (ví dụ: `PERFORMANCE`) có thể xuất hiện nhiều lần trong bài (qua các từ khóa: "pin", "sạc", "tốc độ"). Chúng ta cần gộp các điểm số lẻ tẻ này thành 1 điểm duy nhất.

**Công thức Trung bình Trọng số (Weighted Average):**

$$Score_{final} = \frac{\sum (Score_i \times Confidence_i)}{\sum Confidence_i}$$

  * $Score_i$: Điểm sentiment của mẫu thử $i$ (-1 đến 1).
  * $Confidence_i$: Độ tự tin của model cho mẫu thử đó (0 đến 1).

**Logic Gán nhãn (Labeling):**
Sau khi có $Score_{final}$, dùng ngưỡng (Threshold) để gán nhãn:

  * Score \> 0.25 $\rightarrow$ **POSITIVE**
  * Score \< -0.25 $\rightarrow$ **NEGATIVE**
  * Còn lại $\rightarrow$ **NEUTRAL**

-----

## 3\. Chi tiết Implementation (Python Code)

### Bước 1: Configuration (`src/config/sentiment_config.py`)

Định nghĩa các tham số để dễ tinh chỉnh (Tune) sau này.

```python
class SentimentConfig:
    # Kích thước cửa sổ ngữ cảnh (số ký tự)
    CONTEXT_WINDOW_SIZE = 60 
    
    # Ngưỡng để quyết định Label từ Score
    THRESHOLD_POSITIVE = 0.25
    THRESHOLD_NEGATIVE = -0.25
    
    # Map label của Model ONNX (0, 1, 2) sang ý nghĩa
    # Giả sử model train là: 0=NEG, 1=NEU, 2=POS
    LABEL_MAP = {0: "NEGATIVE", 1: "NEUTRAL", 2: "POSITIVE"}
    SCORE_MAP = {0: -1.0, 1: 0.0, 2: 1.0}
```

### Bước 2: Class `SentimentAnalyzer`

Đây là file chính `src/services/analytics/sentiment_analyzer.py`. Nó sử dụng `PhoBertOnnxAdapter` (đã có từ các bước trước) để chạy inference.

```python
import numpy as np
from typing import List, Dict, Any
from src.adapters.ai.phobert_client import PhoBertOnnxAdapter
from src.config.sentiment_config import SentimentConfig

class SentimentAnalyzer:
    def __init__(self, adapter: PhoBertOnnxAdapter):
        self.ai_adapter = adapter
        self.cfg = SentimentConfig()

    def analyze(self, text: str, keywords: List[Dict]) -> Dict[str, Any]:
        """
        Main entry point.
        Input: Text + List Keywords (from Module 3)
        Output: Overall Sentiment + Aspect Sentiments
        """
        # 1. Phân tích Tổng thể (Overall Sentiment)
        # Chạy model trên toàn bộ text (đã được cắt ngắn nếu quá dài bởi Adapter)
        overall_result = self.ai_adapter.predict(text)

        # 2. Phân tích theo Aspect (Aspect-Based)
        aspect_results = {}
        
        # Gom nhóm keywords theo Aspect (DESIGN, PRICE...)
        # VD: {'PRICE': [kw1, kw2], 'DESIGN': [kw3]}
        grouped_keywords = self._group_keywords_by_aspect(keywords)

        for aspect, kw_list in grouped_keywords.items():
            aspect_scores = []
            
            for kw_data in kw_list:
                # A. CẮT NGỮ CẢNH (The Smart Window Logic)
                context_text = self._extract_smart_window(
                    text, 
                    kw_data['keyword'], 
                    kw_data.get('position', -1)
                )
                
                # B. CHẠY AI CHO NGỮ CẢNH
                # Kết quả: {label: "NEG", score: -0.9, confidence: 0.95}
                result = self.ai_adapter.predict(context_text)
                
                # Lưu lại để tính trung bình
                aspect_scores.append({
                    "score": self._convert_label_to_score(result.label),
                    "confidence": result.confidence,
                    "context": context_text # Lưu để debug
                })

            # C. GỘP ĐIỂM (The Aggregation Logic)
            final_aspect_sentiment = self._aggregate_scores(aspect_scores)
            aspect_results[aspect] = final_aspect_sentiment

        return {
            "overall": overall_result,
            "aspects": aspect_results
        }

    # --- HELPER FUNCTIONS (LOGIC CHI TIẾT) ---

    def _extract_smart_window(self, text: str, keyword: str, position: int) -> str:
        """Logic cắt chuỗi thông minh, không cắt giữa từ"""
        if position == -1: 
            position = text.find(keyword) # Fallback nếu ko có pos
            
        if position == -1: return text # Fallback an toàn

        text_len = len(text)
        radius = self.cfg.CONTEXT_WINDOW_SIZE

        # 1. Xác định biên thô (Raw boundaries)
        start = max(0, position - radius)
        end = min(text_len, position + len(keyword) + radius)

        # 2. Snapping (Mở rộng ra khoảng trắng gần nhất)
        # Tìm khoảng trắng bên trái
        while start > 0 and text[start] != " ":
            start -= 1
        
        # Tìm khoảng trắng bên phải
        while end < text_len and text[end] != " ":
            end += 1
            
        return text[start:end].strip()

    def _aggregate_scores(self, results: List[Dict]) -> Dict:
        """Logic tính trung bình trọng số"""
        if not results: return None

        total_weighted_score = 0.0
        total_confidence = 0.0

        for res in results:
            total_weighted_score += res['score'] * res['confidence']
            total_confidence += res['confidence']

        if total_confidence == 0: return None

        # Điểm trung bình cuối cùng (-1 đến 1)
        final_avg_score = total_weighted_score / total_confidence
        
        # Mapping lại sang Label
        if final_avg_score > self.cfg.THRESHOLD_POSITIVE:
            label = "POSITIVE"
        elif final_avg_score < self.cfg.THRESHOLD_NEGATIVE:
            label = "NEGATIVE"
        else:
            label = "NEUTRAL"

        return {
            "label": label,
            "score": round(final_avg_score, 3),
            "mentions_count": len(results)
        }

    def _convert_label_to_score(self, label: str) -> float:
        """Helper map Label chữ sang số để tính toán"""
        if label == "POSITIVE": return 1.0
        if label == "NEGATIVE": return -1.0
        return 0.0

    def _group_keywords_by_aspect(self, keywords: List[Dict]) -> Dict:
        groups = {}
        for kw in keywords:
            aspect = kw['aspect']
            if aspect not in groups:
                groups[aspect] = []
            groups[aspect].append(kw)
        return groups
```

-----

## 4\. Kế hoạch Kiểm thử (Verification)

Bạn cần tạo test script `examples/sentiment_test.py` với các case sau để verify logic cắt và gộp:

**Test Case 1: Xung đột cảm xúc (Conflict Sentiment)**

  * **Input:** *"Xe này **thiết kế** rất đẹp, nhưng **giá** quá chát."*
  * **Keywords:** `thiết kế (DESIGN)`, `giá (PRICE)`.
  * **Kỳ vọng:**
      * Context 1 ("thiết kế rất đẹp") $\rightarrow$ Model ra POSITIVE.
      * Context 2 ("giá quá chát") $\rightarrow$ Model ra NEGATIVE.
      * **Kết quả:** `aspects: { "DESIGN": "POSITIVE", "PRICE": "NEGATIVE" }`.

**Test Case 2: Gộp điểm (Aggregation)**

  * **Input:** *"**Pin** chán lắm, sạc **3 tiếng** mới đầy, thất vọng về **pin**."*
  * **Keywords:** `pin`, `3 tiếng`, `pin` (3 từ thuộc PERFORMANCE).
  * **Kỳ vọng:** Cả 3 context đều ra NEGATIVE hoặc NEUTRAL $\rightarrow$ Tổng hợp lại ra **NEGATIVE** (Score cao).

-----

### Tổng kết

Module 4 này là sự kết hợp giữa:

1.  **AI (PhoBERT ONNX):** Để hiểu ngữ nghĩa.
2.  **Algorithm (Windowing & Aggregation):** Để định hướng sự tập trung của AI vào đúng chỗ.
