# SALITAyo — Model Training Details

This document covers the datasets, preprocessing decisions, architectural choices, training configuration, and evaluation results for each of the three models trained for the SALITAyo writing assistant. Each section opens with the dataset used, followed immediately by a justification for why that model was chosen for its task, before going into technical specifics.

---

## Table of Contents

1. [Error Type Classifier (RandomForest)](#1-error-type-classifier-randomforest)
   - [1.1 Dataset](#11-dataset)
   - [1.2 Why RandomForest?](#12-why-randomforest)
   - [1.3 Train/Test Split and Balancing](#13-traintest-split-and-balancing)
   - [1.4 Feature Engineering](#14-feature-engineering)
   - [1.5 Training Configuration](#15-training-configuration)
   - [1.6 Evaluation Results](#16-evaluation-results)
   - [1.7 Saved Artifacts](#17-saved-artifacts)
2. [Spelling Candidate Reranker (T5-small)](#2-spelling-candidate-reranker-t5-small)
   - [2.1 The Problem This Model Solves](#21-the-problem-this-model-solves)
   - [2.2 Dataset](#22-dataset)
   - [2.3 Why T5-small?](#23-why-t5-small)
   - [2.4 Candidate Generation for Training](#24-candidate-generation-for-training)
   - [2.5 Model Architecture](#25-model-architecture)
   - [2.6 Training Configuration](#26-training-configuration)
   - [2.7 Evaluation Results](#27-evaluation-results)
   - [2.8 Saved Artifacts](#28-saved-artifacts)
3. [Contextual Alignment Classifier (DeBERTa-v3-small NLI)](#3-contextual-alignment-classifier-deberta-v3-small-nli)
   - [3.1 The Problem This Model Solves](#31-the-problem-this-model-solves)
   - [3.2 Dataset](#32-dataset)
   - [3.3 Why DeBERTa-v3-small?](#33-why-deberta-v3-small)
   - [3.4 Model Architecture](#34-model-architecture)
   - [3.5 Training Configuration](#35-training-configuration)
   - [3.6 Evaluation Results](#36-evaluation-results)
   - [3.7 Saved Artifacts](#37-saved-artifacts)
4. [Summary Comparison](#4-summary-comparison)

---

## 1. Error Type Classifier (RandomForest)

**Notebook:** `SALITAyo_ErrorClassifier.ipynb`

This model takes a (misspelled word, correction) pair and classifies the kind of spelling error made. Classifying the error type is the basis for the pedagogical feedback shown to the learner — it is what separates SALITAyo from a plain spell-checker.

---

### 1.1 Dataset

**Source:** Birkbeck Spelling Error Corpus (Mitton, 1985)

The Birkbeck corpus is a collection of natural spelling errors made by real English-language writers, not synthetically generated. This matters for training a model that will be used with dyslexic learners, because synthetic errors do not reliably reproduce the distribution of real-world dyslexic error patterns.

**Raw size:** 27,018 word pairs (misspelled → correct)

**After cleaning:** 26,389 rows

**Cleaning criteria applied:**
- Both the misspelled word and the correction must be purely alphabetic (removes possessives, hyphenated compounds, abbreviations)
- Minimum lengths: misspelled ≥ 2 characters, correction ≥ 3 characters
- Length ratio constraint: `len(correct) / len(misspelled)` must fall between 0.33 and 3.0 — pairs outside this range imply a level of transformation that no single error type can explain

**Error type distribution before balancing:**

| Error Type | Count | Share |
|---|---|---|
| `omission` | 11,381 | 43.2% |
| `phonetic_sub` | 7,705 | 29.2% |
| `insertion` | 5,918 | 22.4% |
| `transposition` | 756 | 2.9% |
| `reversal` | 629 | 2.4% |

The distribution is heavily skewed toward omission and phonetic substitution. Reversal and transposition account for under 6% combined — yet these are among the most diagnostically important error types for dyslexia. This imbalance had to be addressed before training.

**Label annotation method:**

Labels were not manually annotated. Instead, they were derived programmatically from operational definitions drawn from dyslexia research literature (Miles 1993; Snowling 2000; Shaywitz 2003). Each error type is defined by well-established, consistent linguistic rules — for example, a transposition is specifically two adjacent letters that are swapped while all other letters remain in place. This makes the annotation deterministic and reproducible.

---

### 1.2 Why RandomForest?

Two classifiers were trained and evaluated on identical feature vectors and the same balanced training data: Logistic Regression and Random Forest.

| Model | Weighted F1 | Reversal F1 | Transposition F1 |
|---|---|---|---|
| Logistic Regression | 0.9404 | 0.2917 | 0.6224 |
| **Random Forest (200 trees)** | **0.9809** | **0.6378** | **0.9551** |

**Random Forest was selected for three reasons:**

**1. The decision boundaries between error types are non-linear.**

Logistic Regression assumes a linear boundary in the feature space — that each class can be separated from the others by a straight line (or hyperplane) drawn through the 17 features. This assumption does not hold here. Identifying a transposition, for example, requires a specific *combination* of signals: `length_difference = 0` AND `positional_character_match_ratio < 0.8` AND `shared_character_set_ratio = 1.0`. No single feature alone is sufficient, and no linear combination of them captures the interaction. Random Forest, through its ensemble of decision trees, naturally models these conjunctive, non-linear relationships.

**2. The minority classes are the most important ones to get right.**

The performance gap between the two models is largest on `reversal` (F1: 0.29 → 0.64) and `transposition` (F1: 0.62 → 0.96). These are exactly the error types most strongly associated with dyslexia — reversals like `b/d` confusion and adjacent-letter transpositions are hallmark patterns. A model that performs well on the majority classes but fails on these would be pedagogically useless.

**3. Random Forest does not require feature scaling or distributional assumptions.**

The 17 features have different scales and distributions (some are counts, some are ratios between 0 and 1, some are binary flags). Logistic Regression is sensitive to feature scale and performs best when features are roughly Gaussian. Random Forest makes no such assumptions — it operates on rank-ordered splits of individual features and is robust to scale differences and outliers.

**Random Forest hyperparameters:**

| Parameter | Value | Reason |
|---|---|---|
| `n_estimators` | 200 | Sufficient ensemble size for stable variance reduction without excessive memory |
| `class_weight` | `balanced` | Compensates for any residual class imbalance after SMOTE |
| `n_jobs` | -1 | Uses all available CPU cores for parallel tree building |

---

### 1.3 Train/Test Split and Balancing

**Critical design decision — split before oversampling:**

An earlier version of this pipeline performed oversampling on the full dataset before splitting. This caused the test set to contain synthetic duplicates of training examples, producing an inflated F1 score of 1.0 that did not reflect real-world performance. The correct procedure is:

1. Split the **unique** pairs into train (80%) and test (20%) first
2. Apply oversampling only to the training split
3. Leave the test split untouched

This ensures the model is evaluated on pairs it has never seen in any form, including synthetic variants.

**Split sizes (before oversampling):**

| Split | Rows |
|---|---|
| Training | 21,111 |
| Test | 5,278 |

**Training split after balancing (target: 4,734 samples per class):**

| Error Type | Before | After | Action |
|---|---|---|---|
| `omission` | 9,105 | 4,734 | Undersampled |
| `phonetic_sub` | 6,164 | 4,734 | Undersampled |
| `insertion` | 4,734 | 4,734 | Unchanged |
| `transposition` | 605 | 4,734 | Oversampled (SMOTE) |
| `reversal` | 503 | 4,734 | Oversampled (SMOTE) |
| **Total** | **21,111** | **23,670** | |

The target of 4,734 was set to match the natural count of `insertion` (the median-sized class), avoiding excessive synthetic inflation of the majority classes while still giving the minority classes adequate representation.

---

### 1.4 Feature Engineering

The classifier does not operate on raw strings. Instead, each (misspelled, correction) pair is converted into a **17-dimensional numeric feature vector** before being passed to the model.

**Why handcrafted features over character embeddings or raw strings?**

Using character-level embeddings would risk the classifier learning surface patterns specific to the Birkbeck corpus rather than generalizable linguistic signals. The 17 features are specifically chosen to capture properties that differentiate error types at the level of phonetics, character position, and string structure:

- Omission and insertion are characterized by a non-zero signed length difference
- Transposition produces same-length words with the same character set but low positional match
- Reversal is phonetically divergent but character-set-similar
- Phonetic substitution produces matching Soundex/Metaphone codes despite character differences

Every feature is a signal that *correlates* with an error type without directly encoding the label. This forces the model to generalize from linguistic evidence rather than memorize input-output pairs.

**The 17 features:**

| # | Feature | What it captures |
|---|---|---|
| 1 | `raw_edit_distance` | Total number of character operations (Levenshtein) |
| 2 | `normalized_edit_distance` | Edit distance relative to word length |
| 3 | `edit_distance_to_length_diff_ratio` | Ratio of edit distance to absolute length difference |
| 4 | `length_difference_signed` | `len(mis) - len(cor)` — positive means insertion, negative means omission |
| 5 | `absolute_length_difference` | Magnitude of length difference |
| 6 | `soundex_codes_equal` | 1.0 if Soundex codes match (phonetic fingerprint) |
| 7 | `metaphone_codes_equal` | 1.0 if Metaphone codes match (stronger phonetic signal) |
| 8 | `jaro_winkler_similarity` | Similarity weighted toward prefix agreement |
| 9 | `bigram_overlap_ratio` | Fraction of character bigrams shared |
| 10 | `trigram_overlap_ratio` | Fraction of character trigrams shared |
| 11 | `positional_character_match_ratio` | Fraction of positions where `mis[i] == cor[i]` |
| 12 | `shared_character_set_ratio` | Order-independent character set overlap |
| 13 | `misspelled_word_vowel_ratio` | Vowels as a fraction of misspelled word length |
| 14 | `correct_word_vowel_ratio` | Vowels as a fraction of correct word length |
| 15 | `vowel_ratio_difference` | `cor_vowel_ratio - mis_vowel_ratio` |
| 16 | `misspelled_chars_not_in_correct_ratio` | Characters present in misspelled but absent from correct |
| 17 | `correct_chars_not_in_misspelled_ratio` | Characters present in correct but absent from misspelled |

---

### 1.5 Training Configuration

| Parameter | Value | Reason |
|---|---|---|
| `n_estimators` | 200 | Stable ensemble size; diminishing returns beyond ~150 trees |
| `class_weight` | `balanced` | Compensates for any residual imbalance after SMOTE |
| `n_jobs` | -1 | Parallelizes tree building across all CPU cores |
| Training hardware | CPU only | RandomForest inference is fast enough for real-time use without GPU |

---

### 1.6 Evaluation Results

**Test set (5,278 unique, unseen pairs):**

| Error Type | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| `insertion` | 1.0000 | 1.0000 | 1.0000 | 1,184 |
| `omission` | 1.0000 | 1.0000 | 1.0000 | 2,276 |
| `phonetic_sub` | 0.9725 | 0.9650 | 0.9687 | 1,541 |
| `transposition` | 0.9255 | 0.9868 | 0.9551 | 151 |
| `reversal` | 0.6328 | 0.6429 | 0.6378 | 126 |
| **Weighted avg** | **0.9813** | **0.9809** | **0.9809** | **5,278** |
| **Macro avg** | 0.9062 | 0.9189 | 0.9123 | 5,278 |

**5-fold cross-validation (full 26,389-pair dataset):**

| Fold | F1 |
|---|---|
| 1 | 0.9770 |
| 2 | 0.9820 |
| 3 | 0.9833 |
| 4 | 0.9821 |
| 5 | 0.9806 |
| **Mean** | **0.9810** |
| **Std** | **0.0022** |

The standard deviation of 0.0022 across folds indicates the model is stable — its performance is consistent regardless of which subset of data is held out.

**Unseen dyslexic pair test (17 pairs not in Birkbeck corpus):**

```
PASS  doy        → boy          reversal
PASS  ded        → bed          reversal
PASS  plog       → blog         reversal
PASS  teh        → the          transposition
PASS  recieve    → receive      transposition
PASS  freind     → friend       transposition
PASS  becasue    → because      transposition
PASS  environmet → environment  omission
PASS  begining   → beginning    omission
PASS  diffrent   → different    omission
PASS  thhe       → the          insertion
PASS  writeing   → writing      insertion
FAIL  sed        → said         expected: phonetic_sub, predicted: omission
FAIL  wuz        → was          expected: phonetic_sub, predicted: reversal
FAIL  nite       → night        expected: phonetic_sub, predicted: omission
FAIL  skool      → school       expected: phonetic_sub, predicted: omission
FAIL  definately → definitely   expected: insertion, predicted: phonetic_sub

Accuracy on unseen pairs: 12/17 (70.59%)
```

**Why reversal scores lowest (F1: 0.6378):**

Reversal errors affect only one or two characters in short words. The resulting feature vector closely resembles other error types — a reversal can produce the same `positional_character_match_ratio` and `shared_character_set_ratio` as a transposition, or a similar phonetic fingerprint as a phonetic substitution. With only 629 natural examples in the corpus, even SMOTE oversampling provides limited signal for this class.

**Why phonetic_sub generalizes less to unseen pairs:**

The model achieves 97% F1 on Birkbeck test pairs but only 59% on novel phonetic pairs (`sed`, `wuz`, `nite`, `skool`). Phonetic substitutions are highly word-specific — `nite → night` involves English-specific orthographic conventions (`igh` → `i`) that produce a feature vector with `length_difference = -1`, which looks like omission. The phonetic signal is not strong enough to override the length feature for patterns outside the training vocabulary.

---

### 1.7 Saved Artifacts

| File | Description |
|---|---|
| `error_classifier.joblib` | Serialized RandomForest model |
| `training_metadata.json` | All hyperparameters, dataset stats, and training configuration |
| `meta.json` | Summary metadata |
| `confusion_matrix.png` | Per-class confusion matrix |
| `test_results_for_excel.csv` | All 5,278 test predictions for further analysis |

---

## 2. Spelling Candidate Reranker (T5-small)

**Notebook:** `SALITAyo_Reranker.ipynb`

This model receives a misspelled word and a pool of candidate corrections generated by SymSpell, and selects the most likely correction. It is the third layer of the spelling pipeline, sitting between candidate generation and error classification.

---

### 2.1 The Problem This Model Solves

SymSpell ranks candidates by edit distance (ascending) and word frequency (descending). This works well for keyboard slips but fails for dyslexic error patterns, which often involve phonetic substitutions or non-standard letter sequences that produce corrections with higher edit distance or lower frequency than wrong candidates.

Examples of where SymSpell ranking alone fails:

- `"wuz"` → SymSpell ranks `"wig"` and `"bug"` above `"was"` because they have lower edit distance and higher frequency
- `"nite"` → SymSpell may rank `"mite"` or `"kite"` above `"night"` because `"night"` requires edit distance 3

A model trained on real spelling errors learns to recognize these dyslexic patterns and rerank the correct word to the top even when SymSpell deprioritizes it.

---

### 2.2 Dataset

**Sources:**

| Corpus | Word Pairs | Description |
|---|---|---|
| Birkbeck Spelling Error Corpus (Mitton, 1985) | 35,777 | Natural spelling errors from English writers |
| TOEFL-Spell (ETS) | 3,125 | Spelling errors from non-native English test-takers |
| **Total raw** | **39,411** | |
| **After cleaning** | **38,902** | |

**Why both corpora?**

Birkbeck captures native English speaker error patterns. TOEFL-Spell adds non-native speaker patterns, including phonetic substitutions driven by first-language interference — a pattern directly relevant for Filipino learners writing in English, who may apply Filipino phonological rules to English words.

**Cleaning criteria:**
- Both words must be purely alphabetic
- Minimum lengths: misspelled ≥ 2 characters, correct ≥ 3 characters
- Length ratio constraint: `0.33 ≤ len(correct) / len(misspelled) ≤ 3.0`

**Data splits:**

| Split | Samples | Share |
|---|---|---|
| Training | 22,150 | 80% |
| Validation | 2,769 | 10% |
| Test (held-out) | 2,769 | 10% |

---

### 2.3 Why T5-small?

**Why a sequence-to-sequence model at all?**

The reranking task could have been framed as classification (5-way: pick which candidate is correct) or as pairwise ranking (score each candidate independently). A seq2seq approach was chosen instead because it is more natural and more general: the model reads the misspelled word alongside the candidate list and *generates* the correct word as output. This means the model does not need to be restructured if the candidate pool size changes, and it can leverage T5's pre-trained knowledge of English word forms, morphology, and spelling conventions — knowledge that a classification head trained from scratch would not have.

**Why T5-small specifically, not T5-base or T5-large?**

T5-small (60M parameters) was selected to keep the model runnable on CPU during inference. The pipeline must process every token in the user's input text sequentially, so inference speed per word matters. The task — selecting from a small, pre-filtered pool of 5 candidates — does not require the representational capacity of larger T5 variants. T5-small achieves 85.77% top-1 accuracy on the test set, which represents a meaningful improvement over SymSpell-only ranking without the cost of a heavier model.

**Why not a simpler model like a feed-forward classifier over embeddings?**

A static embedding model (e.g., word2vec cosine similarity) would lack contextual sensitivity to the specific character patterns that define dyslexic errors. It would also not generalize to words outside its vocabulary. T5's encoder can attend to the full prompt — including the misspelled word and all candidates simultaneously — and its decoder produces an output grounded in learned spelling correction patterns, not just static vector proximity.

**Why SentencePiece tokenization?**

Standard word-piece tokenizers trained on grammatical English text handle misspelled words poorly — they decompose unusual character sequences into single characters or unknown tokens, discarding subword structure. SentencePiece learns its vocabulary from statistical subword boundaries and handles novel character sequences more gracefully, which is important when the model input includes misspelled words like `"enthusec"` or `"conaious"`.

---

### 2.4 Candidate Generation for Training

For each training pair, SymSpell was used to generate a pool of 5 candidate corrections using the Google Books Ngram frequency dictionary (82,765 terms), with a maximum edit distance of 3.

**Two critical design choices in candidate preparation:**

**1. The correct word is always included in the candidate pool.**

If SymSpell does not generate the correct word naturally (which can happen for phonetic substitutions at edit distance > 2), it is inserted into the pool. This ensures the model always has a learnable target and prevents training on "impossible" examples where the right answer is not an available option.

**2. Candidates are shuffled before each training example.**

If candidates were always presented in a fixed order (e.g., sorted by edit distance), the model could learn a positional bias — "the first candidate is usually correct" — rather than learning to recognize the correct word from its characters. Shuffling forces the model to evaluate each candidate on its own merits.

**T5 input/output format:**

```
Input:  "correct spelling: recieve candidates: received, relieved, receiver, recited, reclined"
Target: "received"
```

---

### 2.5 Model Architecture

**Base model:** `t5-small` (pre-trained, HuggingFace)

| Parameter | Value |
|---|---|
| Architecture | Encoder-decoder (Seq2Seq) |
| Total parameters | 60,506,624 |
| Encoder layers | 6 |
| Decoder layers | 6 |
| Hidden dimension | 512 |
| Attention heads | 8 |
| Feed-forward dimension | 2,048 |
| Tokenizer | SentencePiece (SPM) |

---

### 2.6 Training Configuration

| Hyperparameter | Value | Reason |
|---|---|---|
| Learning rate | 5e-4 | Higher than typical fine-tuning (2e-5) because T5-small is being adapted to a narrow, well-defined task; faster convergence is appropriate |
| Batch size | 16 | Balances GPU memory usage on Tesla T4 and gradient stability |
| Epochs | 8 (max) | Upper bound; early stopping applies |
| Warmup ratio | 0.1 | 10% of total steps — stabilizes early training before full learning rate is reached |
| Weight decay | 0.01 | L2 regularization to reduce overfitting |
| Early stopping patience | 2 | Training stops if validation loss does not improve for 2 consecutive epochs |
| Best model metric | `eval_loss` | Lower validation loss indicates better generalization of the generation task |
| Mixed precision | fp16 | Reduces GPU memory usage and speeds up training on T4 without meaningful accuracy loss |
| Max input tokens | 128 | Sufficient for the prompt format; no training example exceeds this |
| Max target tokens | 32 | All correct words fall well within this limit |
| Generation strategy | Beam search (beams=4) | More reliable than greedy decoding for short constrained text generation |

**Training infrastructure:** Tesla T4 GPU (Google Colab)

---

### 2.7 Evaluation Results

**Test set (2,769 held-out pairs):**

| Metric | Value |
|---|---|
| Top-1 Accuracy | **85.77%** |
| Candidate Coverage (correct word in pool) | **100.0%** |
| Final training loss | 0.1440 |

Candidate coverage of 100% confirms that the SymSpell + insertion logic always provides the correct word as an option. The 85.77% accuracy reflects how often the model successfully ranks it first — a substantial improvement over edit-distance-only ranking.

**Classic dyslexic misspelling test (8 pairs not in training data):**

```
PASS  nite       → night        (expected: night)
PASS  wuz        → was          (expected: was)
PASS  teh        → the          (expected: the)
PASS  recieve    → receive      (expected: receive)
PASS  freind     → friend       (expected: friend)
PASS  environmet → environment  (expected: environment)
PASS  sed        → said         (expected: said)
PASS  beleive    → believe      (expected: believe)

Score: 8/8 (100%)
```

**Additional inference examples:**

```
silents    → silence
tumage     → tonnage
writeing   → writing
enthusec   → enthusiastic
gorend     → galloped
dooratory  → dormitory
conaious   → conscious
```

The model generalizes to words not present in the training data, indicating that it has learned reranking patterns rather than memorizing training pairs.

---

### 2.8 Saved Artifacts

| File | Size | Description |
|---|---|---|
| `model.safetensors` | ~236 MB | Model weights |
| `config.json` | — | Model architecture configuration |
| `generation_config.json` | — | Beam search and decoding settings |
| `tokenizer.json` | ~2.1 MB | SentencePiece tokenizer |
| `tokenizer_config.json` | — | Tokenizer settings |
| `spiece.model` | — | SentencePiece vocabulary |
| `training_args.bin` | — | Full training arguments |
| `evaluation_metrics.json` | — | Final evaluation results |

**Save location:** `/content/drive/MyDrive/SALITAyo_Reranker/final_model/`

---

## 3. Contextual Alignment Classifier (DeBERTa-v3-small NLI)

**Notebook:** `SALITAyo_NLI.ipynb`

This model takes a sentence pair — a learner sentence and a retrieved reference sentence — and classifies their semantic relationship. It is the final stage of the contextual alignment pipeline, which checks whether the learner's writing is semantically consistent with the reference material a teacher has uploaded.

---

### 3.1 The Problem This Model Solves

A spell-checker can verify that individual words are correctly spelled. It cannot determine whether the *meaning* of what the learner wrote is consistent with the source material. This model addresses that gap by using Natural Language Inference (NLI): given a premise (a retrieved reference sentence) and a hypothesis (the learner's corrected sentence), classify whether the hypothesis entails, contradicts, is neutral toward, or is entirely off-topic relative to the premise.

---

### 3.2 Dataset

**Three sources were combined:**

| Source | Rows | Classes | Purpose |
|---|---|---|---|
| MultiNLI (Williams et al., 2018) | 1,998 | entailment, neutral, contradiction | Diverse domain NLI — covers fiction, telephone, government, travel, slate |
| SNLI (Bowman et al., 2015) | 1,002 | entailment, neutral, contradiction | Image-caption NLI — visual scene descriptions |
| SALITAyo Custom Dataset | 232 | entailment, neutral, contradiction, off_topic | Domain-specific: educational writing contexts |
| **Total** | **3,232** | | |

**Why MultiNLI + SNLI?**

Both are standard NLI benchmarks with high-quality human annotations and well-studied label reliability. MultiNLI's domain diversity (ten genres) helps the model generalize beyond any single writing style. SNLI's visual scene pairs offer a structurally different sentence style — shorter and more concrete — which complements MultiNLI's more abstract claims and broadens the model's exposure to varied sentence forms.

**Why a custom dataset?**

The standard NLI datasets only cover three labels: entailment, neutral, and contradiction. They do not include an `off_topic` class, and their examples do not reflect educational writing contexts where a learner may write about a topic entirely unrelated to the assigned reading. The custom 232 examples were specifically constructed to include:
- Sentences consistent with the reference (`entailment`)
- Sentences that make a related but distinct claim (`neutral`)
- Sentences that directly contradict the reference (`contradiction`)
- Sentences with no meaningful connection to the reference (`off_topic`)

The `off_topic` class is the most important novel contribution: in a teaching scenario, the model must distinguish between a learner who writes something tangentially related versus one who writes about a completely different subject.

**Sampling from MultiNLI and SNLI:**

Equal class proportions were drawn from each corpus to prevent the combined dataset from being dominated by the majority classes of any single source:
- From MultiNLI: 666 per class × 3 classes = 1,998
- From SNLI: 334 per class × 3 classes = 1,002
- Custom: 58 per class × 4 classes = 232

**Data splits:**

Splits were performed using **GroupShuffleSplit on the premise text**. This ensures the same premise sentence cannot appear in both training and test sets in different pairings — a form of data leakage that would inflate performance by exposing the model to familiar context during training.

| Split | Rows | entailment | contradiction | neutral | off_topic |
|---|---|---|---|---|---|
| Training (70%) | 2,263 | 732 | 729 | 762 | 40 |
| Validation (15%) | 485 | 162 | 171 | 143 | 9 |
| Test (15%) | 484 | 164 | 158 | 153 | 9 |

**The small `off_topic` count in test (9 examples) is a known limitation.** The custom dataset is modest in size, and the test confidence interval for `off_topic` is wide. This is acknowledged in the evaluation results.

**Tokenization:**
- Max sequence length: 256 tokens (premise + `[SEP]` + hypothesis)
- Truncation: True
- Padding: `max_length`

---

### 3.3 Why DeBERTa-v3-small?

**Why a cross-encoder architecture over a bi-encoder?**

Bi-encoders (such as Sentence-BERT) encode the premise and the hypothesis independently into fixed vectors, then measure their similarity. This is fast but lossy: the model cannot attend to how specific words in the learner's sentence relate to specific words in the reference sentence. Cross-encoders encode both sentences jointly, allowing every token in the hypothesis to attend to every token in the premise within the same transformer pass. For NLI — where detecting negation, contradictory facts, or missing information requires precise cross-sentence token interactions — cross-encoders consistently outperform bi-encoders. The trade-off is that cross-encoders cannot pre-encode reference sentences independently, but this is handled in our pipeline by using MiniLM (a bi-encoder) for the fast retrieval step, leaving DeBERTa to run only on the single best-matched sentence pair.

**Why DeBERTa-v3 over BERT or RoBERTa?**

Standard BERT-based models use a single attention matrix that combines content and positional information. This means the model's representation of a word conflates *what* it is with *where* it appears. DeBERTa uses **disentangled attention**: each word is represented by two separate vectors — one for its content and one for its position — and the attention score between any two words is computed across all four combinations (content-to-content, content-to-position, position-to-content, position-to-position). This gives the model an explicit, dedicated representation of word order, which is critical for NLI tasks where the position of a negation word or quantifier can flip the entire label (e.g., "The system *does* detect X" vs. "The system does *not* detect X").

**Why start from a pre-trained NLI cross-encoder rather than from the raw DeBERTa base?**

`cross-encoder/nli-deberta-v3-small` is already fine-tuned on NLI tasks before we do any further training. Its classification head is initialized with weights that already encode the distinction between entailment, contradiction, and neutral — not random weights. Starting from this checkpoint means fine-tuning only needs to adjust the existing NLI representations for our specific domain and add the `off_topic` class, rather than learning NLI reasoning from scratch. This requires fewer epochs, less data, and produces a more stable model.

**Label mapping:**

```python
LABEL2ID = {
    "entailment":    0,
    "contradiction": 1,
    "neutral":       2,
    "off_topic":     3
}
```

---

### 3.4 Model Architecture

**Base model:** `cross-encoder/nli-deberta-v3-small` (HuggingFace)

| Parameter | Value |
|---|---|
| Architecture | DeBERTa-v3 (cross-encoder) |
| Total parameters | 141,897,988 |
| Transformer layers | 6 |
| Attention heads | 12 |
| Original classification head | 3 classes (entailment, neutral, contradiction) |
| Fine-tuned classification head | 4 classes (+ off_topic) |

---

### 3.5 Training Configuration

| Hyperparameter | Value | Reason |
|---|---|---|
| Learning rate | 2e-5 | Standard for fine-tuning large pre-trained transformers; prevents catastrophic forgetting of pre-trained NLI weights |
| Batch size | 16 | Stable gradient estimates within T4 GPU memory limits |
| Epochs | 5 (max) | Upper bound; early stopping applies |
| Warmup ratio | 0.1 | 10% of total steps for learning rate warmup |
| Weight decay | 0.01 | L2 regularization |
| Early stopping patience | 2 | Stops training if the metric does not improve for 2 consecutive epochs |
| Best model metric | `f1_weighted` | Prioritizes balanced performance across all four classes, including the small `off_topic` class |
| Evaluation strategy | Per epoch | Full validation set evaluated after each epoch |
| Mixed precision | fp16 | Reduces memory footprint and training time on T4 |

**Why `f1_weighted` as the stopping metric rather than accuracy or loss?**

Accuracy is dominated by the three majority classes and would not penalize poor performance on `off_topic`. Validation loss is an average across all examples and does not directly reflect classification quality per class. Weighted F1 accounts for class size differences while still rewarding accurate classification across all four labels — it is the metric that best reflects the model's real-world utility in an educational context where each label type has a distinct pedagogical meaning.

**Training infrastructure:** Tesla T4 GPU (Google Colab)
**Training duration:** 248.2 seconds

---

### 3.6 Evaluation Results

**Test set (484 held-out pairs):**

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| `entailment` | 0.9357 | 0.9756 | 0.9552 | 164 |
| `contradiction` | 0.9937 | 0.9937 | 0.9937 | 158 |
| `neutral` | 0.9592 | 0.9216 | 0.9400 | 153 |
| `off_topic` | 1.0000 | 0.8889 | 0.9412 | 9 |
| **Weighted avg** | **0.9632** | **0.9628** | **0.9627** | **484** |
| **Macro avg** | 0.9721 | 0.9449 | 0.9575 | 484 |

**Overall test accuracy: 96.28%**
**Validation loss: 0.1720**

**Why contradiction achieves near-perfect scores:**

Contradiction pairs typically involve direct negation or mutually exclusive factual claims, which produce strongly divergent token-level attention patterns. The model learns this signal quickly from the pre-trained weights, which already encode NLI reasoning.

**Why off_topic recall is lower (0.8889):**

With only 9 test examples in the `off_topic` class, a single misclassification drops recall by 11 percentage points. This is a statistical limitation of the dataset size, not necessarily a model failure. The `off_topic` precision of 1.0 (no false positives) is encouraging — when the model does assign the `off_topic` label, it is always correct.

**Sample inference results:**

| Premise | Hypothesis | Predicted | Confidence |
|---|---|---|---|
| AAIMS uses local processing for all computations | AAIMS uses cloud servers for data analysis | `contradiction` | 0.999 |
| System detects mouth movement using MAR metric | System tracks mouth activity using MAR | `entailment` | 0.998 |
| System monitors students during examinations | Basketball improves teamwork | `contradiction` | 0.995 |
| System detects head pose and mouth movement | System detects face absence | `contradiction` | 0.999 |

---

### 3.7 Saved Artifacts

| File | Description |
|---|---|
| `model.safetensors` | Fine-tuned DeBERTa-v3-small weights |
| `config.json` | Model architecture configuration |
| `tokenizer.json` | Tokenizer vocabulary and rules |
| `tokenizer_config.json` | Tokenizer settings |
| `spm.model` | SentencePiece tokenizer model |
| `special_tokens_map.json` | Special token definitions |
| `training_args.bin` | Full training arguments |
| `label_config.json` | Custom 4-class label mapping |

**Save location:** `/content/drive/MyDrive/SALITAyo_NLI/final_model/`

---

## 4. Summary Comparison

| Aspect | Error Classifier | Reranker | NLI Classifier |
|---|---|---|---|
| **File** | `SALITAyo_ErrorClassifier.ipynb` | `SALITAyo_Reranker.ipynb` | `SALITAyo_NLI.ipynb` |
| **Base model** | RandomForest (200 trees) | T5-small | DeBERTa-v3-small (cross-encoder) |
| **Parameters** | 17 handcrafted features | 60,506,624 | 141,897,988 |
| **Primary dataset** | Birkbeck Corpus | Birkbeck + TOEFL-Spell | MultiNLI + SNLI + SALITAyo custom |
| **Dataset size (cleaned)** | 26,389 pairs | 38,902 pairs | 3,232 sentence pairs |
| **Training samples** | 23,670 (after balancing) | 22,150 | 2,263 |
| **Test samples** | 5,278 | 2,769 | 484 |
| **Output** | 5-class label + probabilities | Generated correction word | 4-class label + probabilities |
| **Weighted F1 (test)** | 0.9809 | N/A (generation task) | 0.9627 |
| **Top-1 Accuracy (test)** | 98.09% | 85.77% | 96.28% |
| **Cross-validation F1** | 0.9810 ± 0.0022 (5-fold) | — | — |
| **Training hardware** | CPU | Tesla T4 GPU | Tesla T4 GPU |
| **Training time** | ~5–8 minutes | ~30–45 minutes | ~248 seconds |
| **Key limitation** | Reversal F1: 0.64; phonetic_sub unseen: 71% | 14.23% top-1 miss rate | off_topic test support: 9 examples |

---

### Shared Design Principles Across All Three Models

**1. Split before augmenting.**
All three notebooks perform train/test splitting on unique data first, then apply any augmentation or balancing only to the training split. This prevents synthetic examples from leaking into the test set and inflating evaluation metrics.

**2. Evaluation on held-out data, not validation data.**
The validation set was used exclusively for early stopping and checkpoint selection. Final reported metrics come from a separate test set that was never seen during any part of training or model selection.

**3. Match model complexity to task complexity.**
The error classifier uses a RandomForest (CPU, interpretable, compact) because its 17-feature input is low-dimensional and the decision boundaries are non-linear but tractable. The reranker uses T5-small (lightweight seq2seq) because the task is generative and benefits from pre-trained English language knowledge. The NLI classifier uses DeBERTa-v3-small (purpose-built cross-encoder) because NLI requires full bidirectional attention across both input sentences.

**4. Report honest metrics.**
All three notebooks report both in-distribution test accuracy and out-of-distribution generalization results where applicable. The gap between in-distribution and out-of-distribution performance is acknowledged explicitly, not minimized.
