# SALITAyo — Personal Study Guide

> This guide walks through exactly what happens to your input, step by step, using real examples and numbers you can verify in Excel. Read this before a thesis defense.

---

## Table of Contents

1. [What the app does in one paragraph](#1-what-the-app-does-in-one-paragraph)
2. [The 4 routing cases](#2-the-4-routing-cases)
3. [Following "recieved" through the English pipeline](#3-following-recieved-through-the-english-pipeline)
4. [Edit distance — computing it by hand and in Excel](#4-edit-distance--computing-it-by-hand-and-in-excel)
5. [The 17 features — what they measure and how to compute each](#5-the-17-features--what-they-measure-and-how-to-compute-each)
6. [Filipino and Taglish pipelines — why Groq, not a trained model](#6-filipino-and-taglish-pipelines--why-groq-not-a-trained-model)
7. [Context alignment — RAG and NLI in plain language](#7-context-alignment--rag-and-nli-in-plain-language)
8. [Likely defense questions and how to answer them](#8-likely-defense-questions-and-how-to-answer-them)

---

## 1. What the app does in one paragraph

A learner types a sentence. The app finds words that look misspelled, suggests the correct spelling, classifies *what kind* of spelling mistake it is (reversal? missing letter? extra letter?), and explains why. Optionally, if a teacher has uploaded a reference passage, it also checks whether the learner's sentences are semantically consistent with that passage. The key research contribution is that most spell-checkers only tell you *that* a word is wrong — SALITAyo tells you *how* it is wrong, which is specifically useful for learners with dyslexia.

---

## 2. The 4 routing cases

When you click **Analyze Writing**, the first thing the backend does is decide *which pipeline* to run. This decision is made in `views.py → _classify_input()`.

```
User sends: { text, target_language }
                    │
         target_language == "english"?  ──► Groq: Taglish-to-English
                    │ no
         target_language == "filipino"? ──► Groq: Taglish-to-Filipino
                    │ no
         (target_language == "auto")
                    │
         Run langdetect on the text
                    │
         Both English AND Filipino        ──► Groq: Taglish-to-Filipino
         probability > 0.15?
                    │ no
         Dominant language == Filipino?   ──► Groq: Filipino spelling
                    │ no
                    └──────────────────────►  English NLP pipeline
```

**Key point for defense:** When the user manually picks Filipino or English, we skip language detection entirely. We trust the user. This avoids the case where `langdetect` misclassifies short Taglish sentences as English (which happens because Taglish sentences often have more English words by count).

---

## 3. Following "recieved" through the English pipeline

Let's trace the single word **"recieved"** (common dyslexic transposition error) all the way through.

---

### Step 1 — Tokenize

The whole input text is split into individual words using this regex:

```
r"[A-Za-z]+"
```

This captures only alphabetic characters. Numbers, punctuation, and spaces are ignored. Each token records its **start** and **end** character position in the original string so the frontend knows exactly where to draw the underline.

Example: `"She recieved the lettre."` produces:

| token    | start | end |
|----------|-------|-----|
| She      | 0     | 3   |
| recieved | 4     | 12  |
| the      | 13    | 16  |
| lettre   | 17    | 23  |

---

### Step 2 — Is it a known word?

Before doing any heavy processing, the pipeline checks: *is this word already correct?*

It runs `SymSpell` at `max_edit_distance=0` — meaning "only return a result if the word is in the dictionary with zero changes." If it finds a match, the word is skipped.

- `"the"` → found at edit distance 0 → **skip**
- `"recieved"` → not found at edit distance 0 → **continue**

---

### Step 3 — Build the candidate pool

This is a three-layer search for possible correct spellings.

**Layer 1: SymSpell Tight (max edit distance = 2)**

SymSpell pre-computes all "delete variants" of every dictionary word, so lookups are nearly instant. At max_ed=2, it finds words that require at most 2 insertions, deletions, or substitutions to become the input word.

For `"recieved"`:
- `received` — edit distance 2 (positions 4 and 5 are transposed: `ie` vs `ei`)
- `relieved` — edit distance 3 → outside range, skipped
- Returns maybe 3–5 candidates sorted by (edit distance ASC, frequency DESC)

**Layer 2: SymSpell Wide (max edit distance = 4)**

Only triggered if Layer 1 returns fewer than 5 candidates, or if the best Layer 1 candidate is already at edit distance 2. This catches phonetic misspellings that are far from the correct word in character-edit space.

Example: `"becuz"` has edit distance 3 from `"because"` → Layer 1 misses it → Layer 2 catches it.

**Layer 3: Wikipedia Common Misspellings**

A flat dictionary of 4,310 real-world misspellings. Simple key lookup:
```
"recieved" → not in dictionary
"becuz"    → "because"   ← found
```
If found, the Wikipedia correction is *appended* to the end of the pool (so the reranker still sees SymSpell candidates first).

Final candidate pool for `"recieved"`: `["received", "relieved", "receiver", "recited", ...]`

---

### Step 4 — T5-small Reranker picks the best candidate

The reranker is a small seq2seq language model (like a miniature version of what powers Google Translate). It was trained on ~22,000 (misspelled, correct) pairs from real dyslexic learner data.

It receives a prompt formatted like this:

```
correct: recieved options: received | relieved | receiver | recited
```

And it generates a single output token:

```
received
```

**Why not just use SymSpell's top candidate directly?**
SymSpell ranks by edit distance, then word frequency. So for `"wuz"`, SymSpell might rank `"bus"` (ed=2, common word) above `"was"` (ed=2, also common). The reranker has learned the *spelling correction context* — it knows `"wuz"` is a phonetic substitution pattern that maps to `"was"`.

---

### Step 5 — The 4 fallback checks

After the reranker picks, 4 sanity checks override it if something looks wrong. These are simple math comparisons on **edit distance**.

Let:
- `ed_reranked` = edit distance between `"recieved"` and the reranker's pick
- `ed_top` = edit distance between `"recieved"` and `candidates[0]` (SymSpell's best)

**Check 0a — Did the reranker pick something further away than SymSpell's top?**
```
if ed_reranked > ed_top:
    return candidates[0]
```
Example: reranker returns `"relieved"` (ed=4), but `candidates[0]` is `"received"` (ed=2) → override.

**Check 0b — Same distance, but fewer shared characters?**
```
if ed_reranked == ed_top:
    count characters in the misspelled word that are NOT in the reranker pick
    count characters in the misspelled word that are NOT in candidates[0]
    if reranker pick shares fewer characters → return candidates[0]
```
This is a tiebreaker. Two candidates at the same edit distance — pick the one that shares more of the original letters.

**Check 1 — Is the reranker's pick suspiciously short?**
```
if len(reranked) < len(word) - 1:
    find longest candidate and return that instead
```
Example: `"importnt"` (8 letters) → reranker picks `"import"` (6 letters, suspiciously short) → find longer candidate like `"important"`.

**Check 2 — Is the edit distance just too high to be believable?**
```
if ed_reranked > len(word) / 2:
    return candidates[0]
```
For a 6-letter word, if the reranker picks something 4 edits away, that's probably wrong. Half the word would need to change.

---

### Step 6 — RandomForest classifies the error type

Now that we know the word is `"recieved"` and the correction is `"received"`, we classify *what kind* of mistake this is.

The RandomForest model takes 17 numbers (features) computed from the `(misspelled, correct)` pair and outputs one of 5 labels:

| Label | What it means | Example |
|---|---|---|
| `phonetic_sub` | A letter was replaced with one that sounds similar | `fone` → `phone` |
| `reversal` | A letter was written backwards | `b` written as `d` |
| `omission` | A letter is missing | `begining` → `beginning` |
| `insertion` | An extra letter was added | `thhe` → `the` |
| `transposition` | Two adjacent letters switched places | `recieved` → `received` |

For `"recieved"` → `"received"`, the classifier should predict `transposition` because `ie` and `ei` are the same letters in reversed order.

---

## 4. Edit distance — computing it by hand and in Excel

**Edit distance (Levenshtein distance)** = the minimum number of single-character operations (insert, delete, substitute) needed to turn one word into another.

This number is used in the candidate ranking, the 4 fallback checks, and 3 of the 17 features. You need to understand this.

---

### The dynamic programming table

To compute edit distance between `"thhe"` and `"the"`:

1. Create a table where rows are the letters of `"thhe"` and columns are the letters of `"the"`.
2. Fill in the first row and column as 0, 1, 2, 3... (cost to delete/insert all characters).
3. Fill each cell using this rule:
   - If the two letters match: copy the diagonal value (no cost)
   - If they don't match: take the minimum of the three neighbors (diagonal, left, top) and add 1

```
     ""   t    h    e
""    0    1    2    3
t     1    0    1    2
h     2    1    0    1
h     3    2    1    1   ← letters match at diagonal? No (h vs e). min(1,1,0)+1 = 1
e     4    3    2    1   ← bottom-right cell = edit distance
```

**Edit distance = 1** (one deletion: remove the extra `h`)

---

### Excel formula for edit distance

You can build this table in Excel exactly:

1. Put `"thhe"` vertically in column A (A2=t, A3=h, A4=h, A5=e)
2. Put `"the"` horizontally in row 1 (B1=t, C1=h, D1=e)
3. In B2, enter: `=IF(A2=B$1, B1, MIN(B1, A2, B$1)+1)` — no wait, this needs to be the cell references not letters. Let me give you the right formula.

**Proper Excel setup:**

| | A | B | C | D | E |
|---|---|---|---|---|---|
| 1 | | *(empty)* | t | h | e |
| 2 | t | =A1+1→**1** | | | |
| 3 | h | =A2+1→**2** | | | |
| 4 | h | =A3+1→**3** | | | |
| 5 | e | =A4+1→**4** | | | |

- Row 1, columns B onward: `=B1+1` filling right (0,1,2,3...)
- Column A, rows onward: `=A1+1` filling down (0,1,2,3...)
- Every other cell (e.g. C3):
  ```
  =IF($A3=C$1, B2, MIN(B2, B3, C2)+1)
  ```
  - `$A3` = current row's letter from word 1
  - `C$1` = current column's letter from word 2
  - `B2` = diagonal (substitution cost)
  - `B3` = left (insertion cost)
  - `C2` = above (deletion cost)

The **bottom-right cell** is the edit distance.

---

### Worked example for your thesis: "recieved" vs "received"

```
recieved: r-e-c-i-e-v-e-d  (8 letters)
received: r-e-c-e-i-v-e-d  (8 letters)
                ^-^  ← positions 4 and 5 are swapped
```

Letters match at positions 1, 2, 3, 6, 7, 8. They differ at positions 4 and 5.

Filling the table, the bottom-right value will be **2** (two substitutions: change `i` to `e` at position 4, and `e` to `i` at position 5).

Note: Standard Levenshtein counts a transposition as *2 operations* (not 1). This is why the `transposition` error type is detectable — when `raw_edit_distance == 2` and the two changed positions are adjacent, the feature vector signals transposition.

---

## 5. The 17 features — what they measure and how to compute each

These 17 numbers are calculated for every `(misspelled, correct)` pair and fed into the RandomForest classifier.

**Running example throughout this section: `"recieved"` → `"received"`**

| # | Feature name | What it measures | Computation | Value for example |
|---|---|---|---|---|
| 1 | `raw_edit_distance` | How many character operations to fix the word | Levenshtein (see §4) | **2** |
| 2 | `normalized_edit_distance` | Edit distance relative to word length | `2 / max(8, 8)` = `2/8` | **0.25** |
| 3 | `length_difference_signed` | Is the misspelled word longer or shorter? | `len("recieved") - len("received")` = `8 - 8` | **0** |
| 4 | `absolute_length_difference` | How different are the lengths? | `abs(0)` | **0** |
| 5 | `soundex_equal` | Do they sound the same? | Soundex("recieved") = R230, Soundex("received") = R230 → match | **1.0** |
| 6 | `metaphone_equal` | Do they sound the same? (different phonetic algorithm) | Metaphone both → "RSVT" → match | **1.0** |
| 7 | `jaro_winkler` | String similarity (0–1), weights prefix matches more | Library call: `jellyfish.jaro_winkler("recieved","received")` | **~0.975** |
| 8 | `bigram_overlap` | How many 2-letter pairs are shared? | See below | **~0.75** |
| 9 | `trigram_overlap` | How many 3-letter pairs are shared? | See below | **~0.71** |
| 10 | `positional_match` | What fraction of positions have the same letter? | 6 out of 8 positions match → `6/8` | **0.75** |
| 11 | `shared_char_set` | What fraction of unique letters are shared? | Both words use {r,e,c,i,v,d} → full overlap | **1.0** |
| 12 | `mis_vowel_ratio` | Fraction of vowels in misspelled word | vowels in "recieved" = e,i,e,e = 4 → `4/8` | **0.5** |
| 13 | `cor_vowel_ratio` | Fraction of vowels in correct word | vowels in "received" = e,e,i,e = 4 → `4/8` | **0.5** |
| 14 | `vowel_ratio_diff` | Did vowel count change? | `0.5 - 0.5` | **0.0** |
| 15 | `misspelled_chars_not_in_correct_ratio` | Letters in misspelled that don't appear in correct at all | All chars of "recieved" appear in "received" → `0/8` | **0.0** |
| 16 | `correct_chars_not_in_misspelled_ratio` | Letters in correct that don't appear in misspelled at all | Same — full overlap → `0/8` | **0.0** |
| 17 | `edit_distance_to_length_diff_ratio` | Edit distance relative to length difference | `2 / (abs(0) + 1)` = `2/1` | **2.0** |

---

### How to compute bigram overlap (feature 8)

A **bigram** is every pair of consecutive letters.

```
"recieved" bigrams: re, ec, ci, ie, ev, ve, ed
"received" bigrams: re, ec, ce, ei, iv, ve, ed
```

Intersection: `{re, ec, ve, ed}` = 4 shared
Union: `{re, ec, ci, ie, ev, ve, ed, ce, ei, iv}` = 10 total

`bigram_overlap = 4 / 10 = 0.4`

You can do this in Excel: just list all bigrams in two columns, then use `COUNTIF` to count matches.

---

### How to compute positional match (feature 10)

Write both words vertically, letter by letter, same position:

| Position | recieved | received | Match? |
|---|---|---|---|
| 1 | r | r | ✓ |
| 2 | e | e | ✓ |
| 3 | c | c | ✓ |
| 4 | i | e | ✗ |
| 5 | e | i | ✗ |
| 6 | v | v | ✓ |
| 7 | e | e | ✓ |
| 8 | d | d | ✓ |

Matches: 6 out of 8 → `positional_match = 6/8 = 0.75`

In Excel: `=EXACT(MID(misspelled,n,1), MID(correct,n,1))` for each row, then average.

---

### Why transposition produces this specific pattern

For `"recieved"` → `"received"`, notice:
- `raw_edit_distance` = 2 (two substitutions needed)
- `length_difference_signed` = 0 (same length)
- `positional_match` = 0.75 (most positions match)
- `shared_char_set` = 1.0 (no new or missing letters)
- `mis_vowel_ratio` = `cor_vowel_ratio` (vowel count unchanged)

This combination — *high positional match, zero length difference, zero new characters, edit distance 2* — is the fingerprint the RandomForest learned for transpositions. Compare it to insertion (`"thhe"` → `"the"`): there, `length_difference_signed = +1`, `absolute_length_difference = 1`, and `raw_edit_distance = 1`. Completely different signature.

---

## 6. Filipino and Taglish pipelines — why Groq, not a trained model

### Why no trained model for Filipino

The English pipeline uses two custom-trained models (T5 reranker and RandomForest classifier) built from the **Birkbeck Spelling Error Corpus** and **TOEFL-Spell** dataset. These are large, publicly available corpora of real dyslexic and learner spelling errors.

For Filipino, **no equivalent corpus exists**. There is no large annotated dataset of Filipino dyslexic learner misspellings. This is the exact research gap the paper addresses:

> *Existing assistive technologies for dyslexic learners are heavily Western-centric, trained on English corpora, and cannot serve learners whose primary language is Filipino or who write in Taglish.*

The solution: use a large language model (Groq's `llama-3.3-70b-versatile`) that already knows Filipino grammar and vocabulary. We give it a carefully written prompt that instructs it to find spelling errors (or translate Taglish) and return results in a structured JSON format.

### What the Groq call looks like

The backend sends this to the Groq API:

```
Ikaw ay isang spelling error detector para sa mga mag-aaral na may dyslexia 
na sumusulat sa Filipino o Tagalog.

Suriin ang teksto sa ibaba para sa mga spelling error...
[full prompt]

Teksto: "Ang bta ay kumaikn ng kanin sa paarlan ngayon."
```

Groq returns a JSON array:
```json
[
  { "word": "bta", "correction": "bata", "error_type": "omission", ... },
  { "word": "kumaikn", "correction": "kumakain", "error_type": "transposition", ... },
  { "word": "paarlan", "correction": "paaralan", "error_type": "omission", ... }
]
```

The backend then runs the same position-finding code (`re.finditer`) to map each flagged word back to its exact character position in the original text, so the frontend can highlight it.

### Taglish: why apply changes word-by-word matters

When converting Taglish to pure Filipino or pure English, the model returns individual word (or phrase) substitutions. The corrections are applied *in order, offset-adjusted* — each replacement shifts the character positions of everything that comes after it. The code in `_run_groq()` does this:

```python
offset = 0
for err in errors:
    adj_start = err["start"] + offset
    adj_end   = err["end"]   + offset
    best = err["correction"]
    corrected = corrected[:adj_start] + best + corrected[adj_end:]
    offset += len(best) - (err["end"] - err["start"])
```

This is why the **corrected text** at the top of results shows the full converted sentence, while the **error cards** show each individual word replacement.

---

## 7. Context alignment — RAG and NLI in plain language

This feature is only available when a teacher has uploaded a reference passage.

### Stage 1: Split into sentences

Both the learner's text and the reference passage are cut into individual sentences using spaCy (a standard NLP library). This is necessary because NLI works on sentence pairs, not full paragraphs.

### Stage 2: Retrieve the most relevant reference sentence (RAG)

For each learner sentence, the system finds the *most semantically similar* sentence in the reference passage.

**How**: Both sentences are converted to number vectors (embeddings) by a small model called `paraphrase-MiniLM-L3-v2`. Think of it as each sentence becoming a list of 384 numbers that represents its meaning. Two sentences about the same topic will have similar numbers; two sentences about different topics will not.

The similarity is measured as **cosine similarity** — essentially the angle between the two vectors. A value of 1.0 = identical meaning, 0.0 = completely unrelated.

**You can explain this in defense as:** *"We represent each sentence as a point in 384-dimensional space. The sentence closest in direction to the learner's sentence is the most relevant reference sentence."*

### Stage 3: NLI — what is the logical relationship?

**NLI = Natural Language Inference.** Given two sentences (premise and hypothesis), classify their logical relationship.

The DeBERTa model was fine-tuned to output one of 4 labels:

| Label | What it means | UI colour |
|---|---|---|
| `entailment` | The learner's sentence is consistent with / supported by the reference | Green — "Fits context" |
| `contradiction` | The learner's sentence says the opposite of the reference | Red — "Conflicts" |
| `neutral` | The learner's sentence is about the same topic but makes a different (not contradictory) claim | Grey — "Neutral" |
| `off_topic` | The learner's sentence has no meaningful connection to the reference | Purple — "Off-topic" |

**Example:**
- Reference: *"The fox jumped over the fence."*
- Learner: *"The animal leapt across the barrier."* → `entailment` (same event, different words)
- Learner: *"The fox never moved."* → `contradiction`
- Learner: *"The fox was brown."* → `neutral` (related but makes a different claim)
- Learner: *"The weather was cold."* → `off_topic`

---

## 8. Likely defense questions and how to answer them

---

**Q: Why did you use edit distance instead of just checking if the word is in the dictionary?**

A: Dictionary lookup only tells you *whether* a word is wrong. It cannot tell you *which word was intended*. Edit distance gives a principled way to rank candidates — the smaller the edit distance, the fewer changes needed, the more likely it is the intended word. The reranker then refines this ranking using learned patterns from dyslexic learner data.

---

**Q: How is your system different from a regular spell-checker like Microsoft Word?**

A: Standard spell-checkers flag errors and suggest corrections but do not classify *what type* of error was made. SALITAyo classifies the error into five dyslexia-specific categories (reversal, omission, insertion, transposition, phonetic substitution), which allows pedagogically targeted feedback — telling a learner *why* their spelling is wrong, not just that it is.

---

**Q: Why RandomForest instead of a neural network for the error classifier?**

A: The feature engineering step (17 interpretable features) captures the linguistic knowledge we care about — edit distance, phonetic similarity, length, vowel ratios. A RandomForest on these 17 features achieves F1=0.981 with fast CPU inference, no GPU requirement, and the decision process is interpretable (feature importances can be inspected). A neural network would need substantially more data to learn these patterns from scratch and would be harder to explain.

---

**Q: Why is the Filipino pipeline an LLM call instead of a trained model?**

A: No annotated Filipino dyslexic learner corpus exists at the scale needed to train a custom model. The Birkbeck corpus (22,000 English pairs) has no Filipino equivalent. Using a large language model that already knows Filipino grammar and vocabulary through its training on multilingual web data is the pragmatic solution — and it directly addresses the research gap of Western-centric assistive technology by enabling Filipino-language support.

---

**Q: What does "entailment" mean and how does the model detect it?**

A: Entailment means the learner's sentence logically follows from the reference sentence. The DeBERTa model was fine-tuned on thousands of sentence pairs that were human-labelled as entailment, contradiction, or neutral (MultiNLI and SNLI datasets). It learned what sentence structures and vocabulary patterns correlate with each label. We added a fourth label, `off_topic`, for pairs with no semantic connection.

---

**Q: What are the limits of the system?**

A: Three main limitations:
1. **English pipeline only detects spelling, not grammar.** Subject-verb disagreement, wrong tense, and word order are out of scope.
2. **Taglish conversion can produce grammatically awkward output.** The model replaces words/phrases individually without restructuring the full sentence, so the result may be lexically correct but grammatically imperfect.
3. **The classifier was trained on adult learner data.** Birkbeck and TOEFL-Spell contain university student and EFL test taker errors. Child dyslexic writers may produce patterns underrepresented in that training data, which is why the unseen-pair accuracy (70.6%) is lower than the overall F1 (98.1%).

---

*Good luck tomorrow. You built this. You can explain it.*
