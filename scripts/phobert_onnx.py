# -*- coding: utf-8 -*-
"""
PhoBERT Sentiment Classification - Fine-tuning and ONNX Export Pipeline.
"""

# Colab requirement installations
!pip install --upgrade transformers optimum[onnxruntime]

from google.colab import drive
import os
import numpy as np
import warnings
from datasets import load_from_disk

# Suppress transformers and future warnings for cleaner output
warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings('ignore', category=FutureWarning)
os.environ['TRANSFORMERS_NO_ADVISORY_WARNINGS'] = '1'
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

# Mount Google Drive to access data
drive.mount('/content/drive')

# Path configuration
zip_path = '/content/drive/MyDrive/SMAP/uit_vsfc_processed_data.zip'
extract_dir = '/content/dataset_temp/'
data_folder_name = 'uit_vsfc_processed_data'
data_dir = os.path.join(extract_dir, data_folder_name)

# Unzip dataset if not already extracted
if os.path.exists(data_dir) and os.path.exists(os.path.join(data_dir, 'dataset_dict.json')):
    print(f"[INFO] Dataset already extracted at {data_dir}, skipping unzip...")
else:
    print(f"[INFO] Extracting dataset from {zip_path}...")
    os.makedirs(extract_dir, exist_ok=True)
    !unzip -q "{zip_path}" -d "{extract_dir}"
    print("[INFO] Dataset extracted successfully")

# Load the dataset from disk
full_dataset = load_from_disk(data_dir)
train_data = full_dataset['train']
val_data = full_dataset['validation']

print(f"[INFO] Loaded train_data with {len(train_data)} samples")
print(f"[INFO] Loaded val_data with {len(val_data)} samples")

from transformers import AutoTokenizer, AutoModelForSequenceClassification
import logging

# Set transformers logging to only output errors
logging.getLogger("transformers").setLevel(logging.ERROR)

# Load PhoBERT model and tokenizer
model_name = "vinai/phobert-base"
tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=False)
model = AutoModelForSequenceClassification.from_pretrained(
    model_name,
    num_labels=3,
    ignore_mismatched_sizes=True
)

print("[INFO] Loaded tokenizer and model successfully")

# Install and setup VnCoreNLP for Vietnamese word segmentation
!pip install vncorenlp
!mkdir -p vncorenlp/models/wordsegmenter
!wget -q https://raw.githubusercontent.com/vncorenlp/VnCoreNLP/master/VnCoreNLP-1.1.1.jar -P vncorenlp/
!wget -q https://raw.githubusercontent.com/vncorenlp/VnCoreNLP/master/models/wordsegmenter/vi-segmenter.rdr -P vncorenlp/models/wordsegmenter/
!wget -q https://raw.githubusercontent.com/vncorenlp/VnCoreNLP/master/models/wordsegmenter/wordsegmenter.rdr -P vncorenlp/models/wordsegmenter/

from vncorenlp import VnCoreNLP

rdrsegmenter = VnCoreNLP(
    address="vncorenlp/VnCoreNLP-1.1.1.jar",
    annotators="wseg",
    max_heap_size='-Xmx4g',
    quiet=False
)

print("[INFO] Initialized VnCoreNLP successfully")

# --- Preprocessing and Tokenization ---

def preprocess(text):
    """
    Applies Vietnamese word segmentation to input text.
    """
    if isinstance(text, list):
        text = " ".join(text)
    segmented_text = " ".join([" ".join(sent) for sent in rdrsegmenter.tokenize(text)])
    return segmented_text

def tokenize_batch(batch):
    """
    Tokenizes a batch of texts after applying VnCoreNLP segmentation.
    """
    segmented_sentences = [preprocess(sent) for sent in batch["sentence"]]
    return tokenizer(segmented_sentences, truncation=True, max_length=128, padding="max_length")

def process_dataset(ds):
    """
    Rename sentiment to labels and tokenize the dataset.
    """
    ds = ds.rename_column('sentiment', 'labels')
    ds = ds.map(
        tokenize_batch,
        batched=True,
        batch_size=64,
        remove_columns=["sentence", "topic"],
        num_proc=1,
        desc="Tokenizing"
    )
    return ds

print("[INFO] Starting tokenization...")

tokenized_train = process_dataset(train_data)
tokenized_val = process_dataset(val_data)

print("[INFO] Tokenization completed successfully")

# --- Trainer Configuration ---

from transformers import TrainingArguments, Trainer, DataCollatorWithPadding
from sklearn.metrics import accuracy_score, f1_score

training_args = TrainingArguments(
    output_dir="./phobert_sentiment",
    per_device_train_batch_size=32,
    per_device_eval_batch_size=64,
    num_train_epochs=3,
    eval_strategy="epoch",
    save_strategy="epoch",
    logging_steps=100,
    learning_rate=2e-5,
    weight_decay=0.01,
    warmup_steps=500,
    load_best_model_at_end=True,
    metric_for_best_model="f1",
    save_total_limit=2,
    report_to="none",
    logging_first_step=True,
    fp16=True,
    gradient_accumulation_steps=1,
    seed=42,
    disable_tqdm=False,
    dataloader_num_workers=2,
    dataloader_pin_memory=True,
)

print("[INFO] Training arguments configured")

def compute_metrics(eval_pred):
    """
    Compute accuracy and F1 score for evaluation.
    """
    logits, labels = eval_pred
    preds = logits.argmax(axis=-1)
    acc = accuracy_score(labels, preds)
    f1 = f1_score(labels, preds, average='weighted')
    return {"accuracy": acc, "f1": f1}

data_collator = DataCollatorWithPadding(tokenizer=tokenizer)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_train,
    eval_dataset=tokenized_val,
    compute_metrics=compute_metrics,
    data_collator=data_collator,
)

print("[INFO] Trainer initialized successfully")
print("[INFO] Starting training...")

train_history = trainer.train()

print("[INFO] Training completed successfully!")
print(f"[INFO] Training loss: {train_history.training_loss:.4f}")

# --- Evaluation ---

print("[INFO] Evaluating on validation set...")
eval_results = trainer.evaluate()
print("[INFO] Evaluation results:")
print(f"  Accuracy: {eval_results['eval_accuracy']:.4f}")
print(f"  F1 Score: {eval_results['eval_f1']:.4f}")
print(f"  Loss: {eval_results['eval_loss']:.4f}")

# --- Save Model ---

print("[INFO] Saving model to ./phobert_sentiment_model...")
trainer.save_model("./phobert_sentiment_model")
tokenizer.save_pretrained("./phobert_sentiment_model")

# Remove pytorch_model.bin if exists, for space efficiency
bin_file = "./phobert_sentiment_model/pytorch_model.bin"
if os.path.exists(bin_file):
    os.remove(bin_file)
    print("[INFO] Removed pytorch_model.bin to save space")

print("[INFO] Model saved successfully to ./phobert_sentiment_model/")

model_files = os.listdir("./phobert_sentiment_model")
print(f"[INFO] Saved files: {', '.join(model_files)}")

# Zip model files for download convenience
!cd ./phobert_sentiment_model && zip -r ../phobert_sentiment_model.zip . && cd ..

print("[INFO] Fine-tuning completed successfully!")

# --- PART 2: EXPORT TO ONNX FORMAT ---

print("="*70)
print("PART 2: EXPORTING TO ONNX FORMAT")
print("="*70)

# Define export paths
onnx_output_dir = "./phobert_sentiment_onnx"
onnx_file = os.path.join(onnx_output_dir, "model.onnx")
onnx_copy = "./phobert_sentiment.onnx"

# Check if ONNX export is required
need_export = True
if os.path.exists(onnx_file):
    onnx_size = os.path.getsize(onnx_file) / (1024 * 1024)
    if onnx_size > 400:
        print(f"[INFO] Valid ONNX model already exists ({onnx_size:.2f} MB)")
        print("[INFO] Skipping export to save time...")
        need_export = False
    else:
        print(f"[WARNING] Existing ONNX is too small ({onnx_size:.2f} MB)")
        print("[INFO] Will re-export ONNX...")
        !rm -rf {onnx_output_dir}

if need_export:
    print("[INFO] Starting ONNX export process...")
    print("[INFO] Using optimum-cli to export.")
    print("[INFO] Export process may take 1-2 minutes.")

    # Step 1: Ensure optimum is installed
    print("[INFO] Installing Optimum library...")
    !pip install -q optimum[onnxruntime]

    # Step 2: Export using optimum-cli
    print("[INFO] Exporting model to ONNX format...")
    !optimum-cli export onnx \
        --model ./phobert_sentiment_model \
        --task text-classification \
        {onnx_output_dir}

    # Step 3: Verifying export result
    if os.path.exists(onnx_file):
        onnx_size = os.path.getsize(onnx_file) / (1024 * 1024)
        print(f"[INFO] ONNX file found: {onnx_file}")
        print(f"[INFO] ONNX model size: {onnx_size:.2f} MB")

        if onnx_size > 400:
            print("="*70)
            print("[INFO] ONNX EXPORT SUCCESSFUL")
            print("="*70)
            print(f"Model size: {onnx_size:.0f}MB (expected)")
            print("Model is ready for production deployment")
            print("Expected inference speedup: 2-3x faster on CPU")
            print("="*70)

            # Copy ONNX model for easy download
            !cp {onnx_file} {onnx_copy}
            print(f"[INFO] Copied to {onnx_copy} for easy download")
        else:
            print("="*70)
            print("[WARNING] ONNX EXPORT POSSIBLY INVALID")
            print("="*70)
            print(f"Model size is only {onnx_size:.2f} MB (expected ~500MB)")
            print("Export completed but file size is lower than expected.")
            print("PyTorch model is a fallback option.")
            print("="*70)
    else:
        print("="*70)
        print("[ERROR] ONNX EXPORT FAILED")
        print("="*70)
        print("ONNX file was not created.")
        print("Possible causes include:")
        print("- Insufficient disk space")
        print("- Optimum version incompatibility")
        print("- Model architecture issues")
        print("Using PyTorch model as fallback.")
        print("="*70)

# --- FINAL OUTPUT SUMMARY ---

print("="*70)
print("PIPELINE COMPLETED SUCCESSFULLY")
print("="*70)

# Print out final training and export summary
print("\nTraining Results:")
print(f"  Accuracy: {eval_results['eval_accuracy']*100:.2f}%")
print(f"  F1 Score: {eval_results['eval_f1']*100:.2f}%")
print(f"  Loss: {eval_results['eval_loss']:.4f}\n")

print("Output Files:")
print("1. phobert_sentiment_model.zip (~450MB): PyTorch model for inference/fine-tuning")

if os.path.exists(onnx_copy):
    onnx_size = os.path.getsize(onnx_copy) / (1024 * 1024)
    if onnx_size > 400:
        print(f"2. phobert_sentiment.onnx ({onnx_size:.0f}MB): ONNX model for production (CPU, fast inference, cross-platform)")

print("="*70)
print("Download Instructions:")
print("="*70)
print("\n# Download PyTorch model")
print("from google.colab import files")
print("files.download('phobert_sentiment_model.zip')")

if os.path.exists(onnx_copy) and os.path.getsize(onnx_copy) / (1024 * 1024) > 400:
    print("\n# Download ONNX model (faster inference, optional)")
    print("files.download('phobert_sentiment.onnx')")

print("="*70)
print("Usage Example: PyTorch")
print("="*70)
print("""
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

# Load fine-tuned PhoBERT model and tokenizer
model = AutoModelForSequenceClassification.from_pretrained("./phobert_sentiment_model")
tokenizer = AutoTokenizer.from_pretrained("./phobert_sentiment_model")

# Inference on segmented text (use the same preprocessing used for training)
with torch.no_grad():
    inputs = tokenizer("your preprocessed text here", return_tensors="pt")
    outputs = model(**inputs)
    prediction = torch.argmax(outputs.logits, dim=-1)
""")

if os.path.exists(onnx_copy) and os.path.getsize(onnx_copy) / (1024 * 1024) > 400:
    print("="*70)
    print("Usage Example: ONNX")
    print("="*70)
    print("""
from optimum.onnxruntime import ORTModelForSequenceClassification
from transformers import AutoTokenizer

# Load ONNX converted model and tokenizer
model = ORTModelForSequenceClassification.from_pretrained("./phobert_sentiment_onnx")
tokenizer = AutoTokenizer.from_pretrained("./phobert_sentiment_onnx")

# Inference (same API as regular transformers)
inputs = tokenizer("your preprocessed text here", return_tensors="pt")
outputs = model(**inputs)
""")

print("="*70)
print("Next Steps:")
print("="*70)
print("- Download model files using the above commands")
print("- Test locally or deploy in your application")
print("- Monitor model performance and update if needed")
print("="*70)