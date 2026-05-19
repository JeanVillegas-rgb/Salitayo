# T5 Fine-Tuning for Text Restructuring

This directory contains the machine learning pipeline for fine-tuning a T5 model to perform general text restructuring.

## 📚 Overview

Instead of relying on LLM APIs (prompt engineering), we train a specialized model using:
- **Transfer Learning**: Pre-trained T5 model from Hugging Face
- **Task-Pattern Data**: Mixed original/restructured pairs from many domains
- **Synthetic Examples**: Generated training pairs based on restructuring principles
- **Evaluation Metrics**: BLEU, BERTScore, readability analysis

The model learns the restructuring behavior, not the subject matter. If the examples teach the model how to rewrite a sentence, it can apply that pattern to medical, legal, cooking, academic, or casual text.

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

New packages added:
- `datasets` - Hugging Face dataset library
- `numpy` - Numerical operations
- `scikit-learn` - ML utilities
- `pandas` - Data handling
- `tensorboard` - Training visualization

### 2. Train the Model

```bash
python manage.py train_t5 --epochs 3 --batch-size 8
```

This works without a dataset file because the trainer includes mixed synthetic examples by default.

If you have your own pairs file, pass it with `--data-file`:

```bash
python manage.py train_t5 --epochs 3 --batch-size 4 --model t5-small --data-file training_pairs.jsonl
```

## ☁️ Google Colab Workflow

Use Colab if you want a GPU, more RAM, or easier long training runs. This is the best option if you want to train on 1,000 to 2,000+ pairs.

### Step 1: Prepare a mixed dataset

Create a CSV, JSON, or JSONL file with many `original` and `restructured` pairs. The topic can change from row to row. What matters is the rewrite pattern.

Recommended JSONL example:

```json
{"original": "The article explains the result.", "restructured": "The article explains the result.", "source": "academic"}
{"original": "Please restart the app after the update.", "restructured": "Restart the app after the update.", "source": "instruction"}
```

Aim for at least 1,000 to 2,000 pairs so the model sees enough variety to learn the restructuring task itself.

### Step 2: Put the dataset in Google Drive

Save the file somewhere like:

```text
/MyDrive/salitayo/training_pairs.jsonl
```

### Step 3: Open Colab and mount Drive

In a Colab notebook cell:

```python
from google.colab import drive
drive.mount('/content/drive')
```

### Step 4: Get the project into Colab

If the code is in GitHub:

```python
!git clone <your-repo-url>
%cd restructurer/backend
```

If the project is already in Drive, change into the backend folder there.

### Step 5: Install dependencies

```python
!pip install -r requirements.txt
```

### Step 6: Train on the task dataset

```python
!python manage.py train_t5 --epochs 3 --batch-size 4 --model t5-small --data-file /content/drive/MyDrive/salitayo/training_pairs.jsonl
```

Start with `t5-small`. It is much lighter than `t5-base` and is the safer first Colab run.

### Step 7: Evaluate the model

```python
!python manage.py evaluate_model --sample-size 5
```

### Step 8: Save the model back to Drive

```python
!cp -r models/t5_restructurer /content/drive/MyDrive/salitayo/t5_restructurer
```

### Step 9: Use the learned pattern

After training, the model should generalize to new text topics because it learned the restructuring pattern, not just one subject.

**Options:**
- `--epochs N` - Number of training epochs (default: 3)
- `--batch-size N` - Batch size (default: 8)
- `--learning-rate LR` - Learning rate (default: 2e-5)
- `--model {t5-small,t5-base,t5-large}` - Model size (default: t5-base)
- `--data-file PATH` - Optional CSV, JSON, or JSONL file with `original` and `restructured` pairs

**Output:**
- Trained model saved to: `backend/models/t5_restructurer/`
- Training logs: `backend/models/t5_restructurer/logs/`

### 3. Evaluate the Model

```bash
python manage.py evaluate_model --sample-size 5
```

This runs the model on 5 test cases and shows:
- Restructured output
- Readability metrics (grade level, sentence length)
- Compression ratio
- Vocabulary preservation

### 4. Generate Predictions

```bash
python manage.py train_t5 --predict "Your academic text here"
```

## 📂 Module Structure

### `general_training_data.py`
**Purpose:** Collect and format task-based training data

**Main Class:** `GeneralTrainingDataCollector`
- `load_pair_file()` - Load CSV, JSON, or JSONL pair data
- `create_synthetic_pairs()` - Generate mixed-domain training examples
- `collect_all_pairs()` - Combine all sources
- `save_training_data()` - Export to JSONL/CSV
- `get_train_test_split()` - Create train/test split

**Example:**
```python
from pathlib import Path
from restructurer.general_training_data import GeneralTrainingDataCollector

collector = GeneralTrainingDataCollector()
pairs = collector.collect_all_pairs(Path("training_pairs.jsonl"))
train, test = collector.get_train_test_split(test_size=0.2)
```

### `training_engine.py`
**Purpose:** Fine-tune T5 model

**Main Class:** `T5FineTuner`
- `prepare_data()` - Tokenize and prepare datasets
- `train()` - Run training loop
- `evaluate()` - Test on evaluation set
- `predict()` - Generate restructured text
- `save_model()` - Save fine-tuned model
- `load_model()` - Load saved model
- `get_model_stats()` - Display model info

**Example:**
```python
from pathlib import Path
from restructurer.training_engine import T5FineTuner

tuner = T5FineTuner(model_name="t5-base")
tuner.train(pair_file=Path("training_pairs.jsonl"), num_epochs=3)
tuner.evaluate()

# Later, use the model
prediction = tuner.predict("Your text here")
```

### `model_evaluator.py`
**Purpose:** Comprehensive evaluation metrics

**Main Class:** `TextEvaluator`
- `bleu_score()` - Token overlap with reference
- `bert_score_similarity()` - Semantic similarity
- `readability_metrics()` - Flesch-Kincaid grade
- `compression_ratio()` - Text length reduction
- `vocabulary_simplicity()` - Vocabulary changes
- `evaluate_pair()` - Full evaluation of one pair
- `batch_evaluate()` - Aggregate metrics for multiple pairs

**Metrics Returned:**
```json
{
  "readability": {
    "avg_word_length": 5.2,
    "avg_sentence_length": 15.3,
    "syllable_ratio": 1.4,
    "readability_grade": 6.2
  },
  "compression": 0.75,
  "vocabulary": {
    "original_unique_words": 42,
    "restructured_unique_words": 38,
    "vocabulary_preserved": 0.85
  },
  "bleu": 0.68,
  "bert_score": {
    "precision": 0.92,
    "recall": 0.89,
    "f1": 0.90
  }
}
```

## 🔧 Django Management Commands

### Train Command

```bash
python manage.py train_t5 [OPTIONS]
```

**Options:**
- `--epochs N` - Training epochs
- `--batch-size N` - Batch size
- `--learning-rate LR` - Learning rate
- `--model {t5-small,t5-base,t5-large}` - Model size
- `--evaluate-only` - Only evaluate (no training)
- `--predict TEXT` - Generate prediction
- `--stats` - Display model statistics

### Evaluate Command

```bash
python manage.py evaluate_model [OPTIONS]
```

**Options:**
- `--sample-size N` - Number of test samples (default: 5)

## 📊 Training Process

```
┌─────────────────────────────────────┐
│ 1. Collect Training Data            │
│    - Load mixed original/restructured pairs │
│    - Generate synthetic task examples       │
│    - 80/20 train/test split                  │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│ 2. Tokenize Data                    │
│    - Convert text to token IDs      │
│    - Pad sequences to max_length    │
│    - Prepare attention masks        │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│ 3. Fine-tune T5 Model               │
│    - Load pre-trained T5            │
│    - Train on restructuring pairs   │
│    - Evaluate every epoch           │
│    - Save best model                │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│ 4. Evaluate Model                   │
│    - Test on unseen examples        │
│    - Calculate BLEU, BERTScore      │
│    - Measure readability improve.   │
└─────────────────────────────────────┘
```

## 💡 Usage Examples

### Python Script

```python
from pathlib import Path
from restructurer.training_engine import T5FineTuner
from restructurer.model_evaluator import TextEvaluator

# Train
tuner = T5FineTuner(model_name="t5-base")
tuner.train(corpus_dir=Path("rag_corpus"), num_epochs=3)

# Evaluate
results = tuner.evaluate()
print(f"Evaluation: {results}")

# Predict
text = "The samples were analyzed by the researchers."
restructured = tuner.predict(text)
print(f"Restructured: {restructured}")

# Detailed metrics
evaluator = TextEvaluator()
metrics = evaluator.evaluate_pair(text, restructured)
print(f"Readability Grade: {metrics['readability']['readability_grade']}")
```

### Django Shell

```bash
python manage.py shell
```

```python
from pathlib import Path
from restructurer.training_engine import T5FineTuner

tuner = T5FineTuner()
tuner.train(pair_file=Path("training_pairs.jsonl"))
```

## 📈 Expected Results

After training on the synthetic + corpus data:

| Metric | Value |
|--------|-------|
| BLEU Score | 0.65-0.75 |
| BERTScore F1 | 0.85-0.92 |
| Readability Grade (Original) | 12-14 |
| Readability Grade (Restructured) | 6-8 |
| Compression Ratio | 0.7-0.8 |
| Vocabulary Preserved | 80-90% |

## 🎓 Computer Science Learning Value

This setup demonstrates:

1. **Transfer Learning** - Using pre-trained models for domain tasks
2. **Data Pipeline** - Collecting, tokenizing, and batching data
3. **Model Fine-tuning** - Adapting models to specific domains
4. **Evaluation Metrics** - Measuring model quality objectively
5. **Hyperparameter Tuning** - Learning rate, batch size, epochs
6. **Production ML** - Saving/loading models, making predictions
7. **Reproducibility** - Fixing random seeds, logging results

## 📝 Training Tips

### Data Quality
- Add more diverse examples to training data
- Balance simple and complex examples
- Include domain-specific vocabulary

### Hyperparameter Tuning
- Start with `t5-small` for faster iteration
- Increase `batch_size` if you have GPU memory
- Lower `learning_rate` if training becomes unstable
- More `epochs` = better performance (up to 5-10)

### Troubleshooting

**Out of Memory Error:**
```bash
python manage.py train_t5 --batch-size 4 --model t5-small
```

**Training too slow:**
- Use GPU if available
- Reduce `max_length` in training_data.py
- Use `t5-small` instead of `t5-base`

**Model not improving:**
- Add more training data
- Check data quality (are pairs realistic?)
- Adjust learning rate

## 📚 References

- Hugging Face Transformers: https://huggingface.co/transformers/
- T5 Paper: https://arxiv.org/abs/1910.10683
- BERT Score: https://github.com/Tiiiger/bert_score
- Flesch-Kincaid Grade: https://en.wikipedia.org/wiki/Flesch%E2%80%93Kincaid_readability_tests

## 🔐 File Structure

```
backend/
├── restructurer/
│   ├── training_data.py          # Data collection & preparation
│   ├── training_engine.py        # Fine-tuning logic
│   ├── model_evaluator.py        # Evaluation metrics
│   ├── management/
│   │   └── commands/
│   │       ├── train_t5.py       # Training command
│   │       └── evaluate_model.py # Evaluation command
│   └── ...other files
├── models/
│   ├── t5_restructurer/          # Fine-tuned model (created after training)
│   └── cache/                    # HuggingFace model cache
└── requirements.txt
```

## ✅ Next Steps

1. ✅ Install dependencies: `pip install -r requirements.txt`
2. 🔄 Train the model: `python manage.py train_t5 --epochs 3`
3. 📊 Evaluate: `python manage.py evaluate_model`
4. 🚀 Deploy: Use trained model in views instead of LLM API
5. 📈 Improve: Add more training data and re-train

---

**Author:** ML Pipeline for SALITAyo Restructurer
**License:** Same as main project
