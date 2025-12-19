# HƯỚNG DẪN LẬP TRÌNH VỚI MODEL PHOBERT ONNX (5-CLASS)

Tài liệu này giải thích chi tiết các câu lệnh Python để Load, Xử lý dữ liệu và chạy Dự đoán với model đã tối ưu.

## 1\. YÊU CẦU CÀI ĐẶT

Trước khi gõ lệnh, môi trường Python cần có các thư viện sau:

```bash
uv add optimum[onnxruntime] transformers pyvi
```

-----

## 2\. CÁC CÂU LỆNH LOAD MODEL (KHỞI TẠO)

Để sử dụng model, bạn cần 2 thành phần: **Tokenizer** (để biến chữ thành số) và **Model Engine** (để tính toán).

### Cấu trúc lệnh:

```python
from transformers import AutoTokenizer
from optimum.onnxruntime import ORTModelForSequenceClassification

# Đường dẫn đến thư mục chứa các file .onnx, config.json, vocab.txt...
model_path = "./phobert/models" 

# 1. Lệnh Load Tokenizer
tokenizer = AutoTokenizer.from_pretrained(model_path)

# 2. Lệnh Load Model (Quan trọng)
model = ORTModelForSequenceClassification.from_pretrained(
    model_path,
    file_name="model_quantized.onnx"  # Bắt buộc phải trỏ đúng tên file model đã nén
)
```

**Giải thích tham số:**

  * `model_path`: Thư mục chứa model.
  * `file_name`: Tên file vật lý của model ONNX. Nếu bạn không khai báo dòng này, nó sẽ tìm file `model.onnx` mặc định (thường là bản chưa nén) -\> **Sai mục đích tối ưu.**

-----

## 3\. CÁC CÂU LỆNH XỬ LÝ DỮ LIỆU (PRE-PROCESSING)

Model không hiểu tiếng Việt thô, bạn **bắt buộc** phải qua 2 bước lệnh này.

### Bước 1: Tách từ (Segmentation)

Dùng thư viện `pyvi` để gom các từ ghép lại với nhau bằng dấu gạch dưới `_`.

```python
from pyvi import ViTokenizer

text_raw = "Sản phẩm chất lượng cao"
text_segmented = ViTokenizer.tokenize(text_raw)

# Kết quả lệnh này: "Sản_phẩm chất_lượng cao"
```

### Bước 2: Mã hóa (Tokenization)

Biến text đã tách từ thành các con số (Tensor) để nạp vào model.

```python
inputs = tokenizer(
    text_segmented,           # Text đã qua PyVi
    return_tensors="pt",      # Trả về định dạng PyTorch Tensor ("pt")
    truncation=True,          # Cắt bớt nếu câu quá dài
    max_length=128,           # Độ dài tối đa (theo lúc train)
    padding="max_length"      # Đệm thêm số 0 nếu câu quá ngắn
)

# inputs lúc này là một Dictionary chứa 'input_ids' và 'attention_mask'
```

-----

## 4\. CÂU LỆNH DỰ ĐOÁN (INFERENCE)

Đây là bước chạy model để ra kết quả.

```python
import torch

# Gọi model (Inference)
with torch.no_grad(): # Tắt tính toán gradient để tiết kiệm RAM/CPU
    outputs = model(**inputs)

# outputs.logits là kết quả thô, ví dụ: [-2.1, 4.5, 0.2, -1.5, -3.0]
```

-----

## 5\. CÂU LỆNH ĐỌC KẾT QUẢ (POST-PROCESSING)

Kết quả thô (`logits`) cần được chuyển đổi thành xác suất và nhãn (Sao).

```python
# 1. Tính Softmax để ra xác suất % (0.0 đến 1.0)
probs = outputs.logits.softmax(dim=1)

# 2. Lấy vị trí có xác suất cao nhất (argmax)
# Ví dụ: [0.01, 0.02, 0.05, 0.90, 0.02] -> Vị trí index số 3 là lớn nhất
pred_label_index = torch.argmax(probs, dim=1).item()

# 3. Tính ra số Sao (Rating)
# Vì index chạy từ 0->4, nên số sao = index + 1
rating_star = pred_label_index + 1

# 4. Lấy độ tin cậy (Confidence score)
confidence = probs[0][pred_label_index].item()
```

-----

## TỔNG HỢP: SNIPPET "MÌ ĂN LIỀN"

Copy đoạn này vào code của bạn là chạy được ngay.

```python
import torch
from pyvi import ViTokenizer
from transformers import AutoTokenizer
from optimum.onnxruntime import ORTModelForSequenceClassification

# --- 1. SETUP ---
PATH = "./phobert_shopee_ONNX"
tokenizer = AutoTokenizer.from_pretrained(PATH)
model = ORTModelForSequenceClassification.from_pretrained(PATH, file_name="model_quantized.onnx")

def predict_rating(text):
    # --- 2. PRE-PROCESS ---
    # Tách từ
    seg_text = ViTokenizer.tokenize(text)
    # Tokenize
    inputs = tokenizer(seg_text, return_tensors="pt", truncation=True, max_length=128, padding="max_length")
    
    # --- 3. INFERENCE ---
    with torch.no_grad():
        outputs = model(**inputs)
    
    # --- 4. POST-PROCESS ---
    probs = outputs.logits.softmax(dim=1)
    label_idx = torch.argmax(probs, dim=1).item()
    
    return {
        "rating": label_idx + 1,        # 1 đến 5 sao
        "score": probs[0][label_idx].item() # Độ tin cậy
    }

# --- CHẠY THỬ ---
print(predict_rating("Hàng dở tệ, phí tiền")) 
# Output: {'rating': 1, 'score': 0.98...}
```