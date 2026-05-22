import { useState, useEffect, useRef, useCallback } from "react";
import {
  wpStartSession as startSession,
  wpSubmitAttempt as submitAttempt,
  wpEndSession as endSession,
  wpGetWords as getWords,
  wpSyncPosTags as syncPosTags,
  wpImportWords as importWords,
} from '../../services/wpApi';

import {
  getDifficultWords,
  removeDifficultWord,
  subscribeDifficultWords,
} from '../../services/difficultWords';

const AUG_LEVEL_LABELS = { 0: "plain", 1: "mild", 2: "intermediate", 3: "severe" };
const HEARTS_MAX = 5;
const SYLLABLE_COLORS = ["#c0392b", "#1a6b3c", "#1a3a6b", "#7d3c98"];

const COPY = {
  en: {
    moduleEyebrow: "Module",
    title: "Word Proficiency",
    subtitle: "Choose a word type to practice pronunciation with adaptive augmentation.",
    langLabel: "Practice language",
    sessionComplete: "Session complete!",
    sessionEnded: "Session ended",
    wordsAssessed: "words assessed",
    heartsLeft: "Hearts left",
    escalated: "Escalated",
    regressed: "Regressed",
    rrApplied: "RR level applied",
    rrSection: "Reading Restructurer summary",
    underAug: "Under-augmented",
    rrCorrect: "RR was right",
    overAug: "Over-augmented",
    wordBreakdown: "Word-by-word",
    backToTypes: "← Back to word types",
    greatJob: "Great job! ✓",
    notQuite: "Not quite ✗",
    youSaid: "You said:",
    noSpeech: "(no speech detected)",
    matchAccuracy: "Match accuracy:",
    sttConfidence: "STT confidence:",
    endEarly: "end session early",
    retryRound: "· retry round",
    speak: "speak",
    recommendation: { increase: "increase", reduce: "reduce", keep: "keep" },
    nowLevel: (n, label) => `→ now L${n} (${label})`,
  },
  fil: {
    moduleEyebrow: "Modyul",
    title: "Kasanayan sa Salita",
    subtitle: "Pumili ng uri ng salita para sanayin ang pagbigkas na may adaptive augmentation.",
    langLabel: "Wika ng pagsasanay",
    sessionComplete: "Tapos na ang sesyon!",
    sessionEnded: "Natapos ang sesyon",
    wordsAssessed: "salitang nasuri",
    heartsLeft: "Natitirang puso",
    escalated: "Tumaas ang antas",
    regressed: "Bumaba ang antas",
    rrApplied: "Inilapat ang antas ng RR",
    rrSection: "Buod ng Reading Restructurer",
    underAug: "Kulang ang augmentation",
    rrCorrect: "Tama ang RR",
    overAug: "Sobra ang augmentation",
    wordBreakdown: "Bawat salita",
    backToTypes: "← Bumalik sa mga uri ng salita",
    greatJob: "Magaling! ✓",
    notQuite: "Hindi pa ✗",
    youSaid: "Sinabi mo:",
    noSpeech: "(walang narinig)",
    matchAccuracy: "Katumpakan ng pagbigkas:",
    sttConfidence: "Kumpiyansa ng STT:",
    endEarly: "tapusin nang maaga ang sesyon",
    retryRound: "· ikalawang pagkakataon",
    speak: "magsalita",
    recommendation: { increase: "dagdagan", reduce: "bawasan", keep: "panatilihin" },
    nowLevel: (n, label) => `→ L${n} na (${label})`,
  },
};

const SEED_WORDS_FIL = {
  NOUN: ["bahay", "aralin", "ulan"],
  VERB: ["bumasa", "sumayaw", "tumakbo"],
  ADJ: ["maganda", "maliit", "matanda"],
  ADV: ["mabilis", "dahan-dahan", "palagi"],
  PRON: ["ako", "ikaw", "sila"],
  DET: ["ang", "mga", "lahat"],
  ADP: ["sa", "mula", "hanggang"],
  CONJ: ["at", "pero", "dahil"],
  NUM: ["isa", "dalawa", "sampu"],
  OTHER: ["kamusta", "salamat", "oo"],
};

const RECOMMENDATION_STYLE = {
  increase: { accent: "#1a6b3c", light: "#e8f5ee", icon: "↑" },
  reduce:   { accent: "#B85C38", light: "#faeaea", icon: "↓" },
  keep:     { accent: "#5C6E42", light: "#f0f4ea", icon: "✓" },
};

const POS_META = {
  NOUN:  { label: "Nouns", icon: "🧱", accent: "#1a3a6b", light: "#e8eef8" },
  VERB:  { label: "Verbs", icon: "⚡", accent: "#1a6b3c", light: "#e8f5ee" },
  ADJ:   { label: "Adjectives", icon: "🎨", accent: "#7d3c98", light: "#f3eaf8" },
  ADV:   { label: "Adverbs", icon: "💨", accent: "#c0392b", light: "#faeaea" },
  PRON:  { label: "Pronouns", icon: "👤", accent: "#b7770d", light: "#fdf3e3" },
  DET:   { label: "Determiners", icon: "🔍", accent: "#2e7d7d", light: "#e6f4f4" },
  ADP:   { label: "Adpositions", icon: "🔗", accent: "#6b4c1a", light: "#f5ede0" },
  CONJ:  { label: "Conjunctions", icon: "🤝", accent: "#4a4a4a", light: "#efefef" },
  NUM:   { label: "Numerals", icon: "🔢", accent: "#5b1a6b", light: "#f0e8f5" },
  OTHER: { label: "Other", icon: "📦", accent: "#555", light: "#f0f0f0" },
};

const SEED_WORDS = {
  NOUN: ["mountain","library","thunder"], VERB: ["whisper","gather","stumble"],
  ADJ: ["brilliant","fragile","ancient"], ADV: ["swiftly","barely","gently"],
  PRON: ["himself","herself","themselves"], DET: ["every","several","each"],
  ADP: ["beneath","beyond","through"], CONJ: ["although","unless","because"],
  NUM: ["dozen","hundred","thousand"], OTHER: ["hello","please","maybe"],
};

const SEED_WORD_TO_POS = Object.fromEntries(
  Object.entries({ ...SEED_WORDS, ...SEED_WORDS_FIL }).flatMap(([pos, arr]) =>
    arr.map((w) => [w.toLowerCase(), pos])
  )
);

function wordLanguage(ws) {
  const raw = ws?.language ?? ws?.features?.language ?? "en";
  return raw === "fil" ? "fil" : "en";
}

function apiPosTag(ws) {
  const raw = ws.pos_tag ?? ws.features?.pos_tag ?? "OTHER";
  const tag = String(raw).toUpperCase().trim();
  return POS_META[tag] ? tag : "OTHER";
}

function resolvePosTag(ws) {
  const key = ws?.word != null ? String(ws.word).toLowerCase().trim() : "";
  const fromSeed = key && SEED_WORD_TO_POS[key];
  const raw = fromSeed ?? ws.pos_tag ?? ws.features?.pos_tag ?? "OTHER";
  const tag = String(raw).toUpperCase().trim();
  return POS_META[tag] ? tag : "OTHER";
}

function normalizeWordEntry(w) {
  if (typeof w === "string") {
    return { word: w, augmentation_level: 0, augmentation_gap: 0, initial_augmentation_level: 0 };
  }
  return {
    ...w,
    augmentation_level: w.augmentation_level ?? 0,
    augmentation_gap: w.augmentation_gap ?? 0,
    initial_augmentation_level: w.initial_augmentation_level ?? 0,
    aug_tier_label: w.aug_tier_label ?? AUG_LEVEL_LABELS[w.augmentation_level ?? 0],
  };
}

/** Merge post-session RR / escalation levels into the POS card word lists. */
function applySessionLevelsToWordsByPos(byPos, endResult) {
  if (!endResult || !byPos) return byPos;
  const levelByWord = new Map();
  for (const r of endResult.classifier_results ?? []) {
    if (r.word != null && r.augmentation_level_after != null) {
      levelByWord.set(String(r.word).toLowerCase(), {
        augmentation_level: r.augmentation_level_after,
        augmentation_gap: 0,
        initial_augmentation_level: r.augmentation_level_after,
        aug_tier_label: r.aug_tier_label_after ?? AUG_LEVEL_LABELS[r.augmentation_level_after],
        status: r.recommendation === "reduce" ? "regressed" : r.recommendation === "increase" ? "escalated" : undefined,
      });
    }
  }
  if (levelByWord.size === 0) return byPos;
  const next = {};
  for (const [pos, list] of Object.entries(byPos)) {
    next[pos] = list.map((w) => {
      const e = normalizeWordEntry(w);
      const patch = levelByWord.get(String(e.word).toLowerCase());
      return patch ? { ...e, ...patch } : e;
    });
  }
  return next;
}

function normalizeForMatch(s) {
  return String(s || "").toLowerCase().normalize("NFC").replace(/[^\p{L}\p{N}]/gu, "");
}

function recommendationLabel(rec, lang) {
  const key = rec?.recommendation ?? "keep";
  return COPY[lang]?.recommendation?.[key] ?? key;
}

/** Client-side fallback when API omits match_accuracy. */
function computeMatchAccuracy(expected, transcript) {
  const exp = normalizeForMatch(expected);
  const got = normalizeForMatch(transcript);
  if (!exp || !got) return 0;
  let matches = 0;
  const len = Math.max(exp.length, got.length);
  for (let i = 0; i < Math.min(exp.length, got.length); i++) {
    if (exp[i] === got[i]) matches += 1;
  }
  return Math.round((matches / len) * 100);
}

function buildAttemptFeedback(responseData, expectedWord, isDemo) {
  const transcript = responseData?.transcript ?? (isDemo ? expectedWord : "");
  const match_accuracy =
    responseData?.match_accuracy ??
    computeMatchAccuracy(expectedWord, transcript);
  return {
    correct: responseData?.correct ?? isDemo,
    transcript,
    match_accuracy,
    confidence: responseData?.confidence ?? null,
  };
}

function splitSyllables(word) {
  const vowels = "aeiouy";
  const parts = [];
  let cur = "", prev = false;
  for (let i = 0; i < word.length; i++) {
    const ch = word[i];
    const v = vowels.includes(ch.toLowerCase());
    if (v && !prev && cur.length > 2) { parts.push(cur.slice(0, -1)); cur = cur.slice(-1); }
    cur += ch; prev = v;
  }
  if (cur) parts.push(cur);
  return parts.length > 0 ? parts : [word];
}

function AugmentedWord({ word, level }) {
  if (!word) return null;
  const base = { fontFamily: "'Lora', serif", fontSize: "2.6rem", fontWeight: 700 };
  if (level === 0) return <span style={base}>{word}</span>;
  const parts = splitSyllables(word);
  return (
    <span style={base}>
      {parts.map((p, i) => (
        <span key={i} style={{ color: level >= 2 ? SYLLABLE_COLORS[i % SYLLABLE_COLORS.length] : "inherit", fontWeight: level >= 3 ? 900 : 700 }}>
          {p}{i < parts.length - 1 && <span style={{ color: "#ccc", fontWeight: 400 }}> · </span>}
        </span>
      ))}
    </span>
  );
}

function Hearts({ count, max = HEARTS_MAX }) {
  return (
    <div style={{ display: "flex", gap: 4 }}>
      {Array.from({ length: max }).map((_, i) => (
        <span key={i} style={{ color: i < count ? "#c0392b" : "#ddd" }}>{i < count ? "♥" : "♡"}</span>
      ))}
    </div>
  );
}

function LanguageToggle({ lang, onChange }) {
  return (
    <div
      role="group"
      aria-label={COPY[lang].langLabel}
      style={{
        display: "inline-flex",
        padding: 3,
        borderRadius: 999,
        background: "var(--sand)",
        border: "1px solid var(--stone)",
        marginBottom: "1.25rem",
      }}
    >
      {[
        { id: "en", label: "English" },
        { id: "fil", label: "Filipino" },
      ].map(({ id, label }) => (
        <button
          key={id}
          type="button"
          onClick={() => onChange(id)}
          style={{
            padding: "0.35rem 0.85rem",
            borderRadius: 999,
            border: "none",
            fontSize: "0.72rem",
            fontWeight: lang === id ? 600 : 400,
            cursor: "pointer",
            background: lang === id ? "var(--white)" : "transparent",
            color: lang === id ? "var(--ink)" : "var(--hint)",
            boxShadow: lang === id ? "0 1px 4px rgba(0,0,0,0.08)" : "none",
          }}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

function ReviewWordsPanel({ words, onPractice, onRemove }) {

  if (!words?.length) return null;

  return (

    <section className="wp-review-panel" aria-label="Words to Review">

      <div className="wp-review-header">

        <div>

          <p className="wp-review-kicker">Reading Restructurer</p>

          <h2>Words to Review</h2>

        </div>

        <button type="button" className="wp-review-practice-btn" onClick={onPractice}>

          Practice these

        </button>

      </div>

      <div className="wp-review-list">

        {words.slice(0, 12).map((item) => (

          <span className="wp-review-chip" key={item.word}>

            <span>

              {item.word}

              <small>clicked {item.clickCount || 1}x</small>

            </span>

            <button
              type="button"
              aria-label={`Remove ${item.word} from review words`}
              onClick={() => onRemove(item.word)}
            >

              x

            </button>

          </span>

        ))}

      </div>

    </section>

  );

}



function RecordButton({ onRecordingComplete, disabled, lang = "en" }) {
  const t = COPY[lang];
  const [recording, setRecording] = useState(false);
  const [countdown, setCountdown] = useState(null);
  const mediaRef = useRef(null);
  const chunksRef = useRef([]);
  const timerRef = useRef(null);

  const stop = () => {
    clearInterval(timerRef.current);
    setCountdown(null);
    setRecording(false);
    if (mediaRef.current?.state !== "inactive") mediaRef.current.stop();
  };

  const start = async () => {
    if (disabled || recording) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      chunksRef.current = [];
      mr.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      mr.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        onRecordingComplete(new Blob(chunksRef.current, { type: "audio/webm" }));
      };
      mr.start(100);
      mediaRef.current = mr;
      setRecording(true);
      let sec = 4;
      setCountdown(sec);
      timerRef.current = setInterval(() => {
        sec -= 1;
        setCountdown(sec);
        if (sec <= 0) stop();
      }, 1000);
    } catch {
      alert("Microphone access denied.");
    }
  };

  return (
    <button type="button" onClick={recording ? stop : start} disabled={disabled && !recording} style={{
      width: 88, height: 88, borderRadius: "50%",
      border: recording ? "3px solid #c0392b" : "3px solid #222",
      background: recording ? "#c0392b" : "#fff",
      color: recording ? "#fff" : "#222",
      cursor: disabled && !recording ? "not-allowed" : "pointer",
    }}>
      <span style={{ fontSize: "1.4rem" }}>{recording ? "⬛" : "🎤"}</span>
      <span style={{ fontSize: "0.62rem" }}>{recording ? `${countdown}s` : t.speak}</span>
    </button>
  );
}

function PosSelectionScreen({ wordsByPos, onSelect, error, lang, onLangChange, reviewWords, onPracticeReviewWords, onRemoveReviewWord }) {
  const t = COPY[lang];
  return (
    <div>
      <LanguageToggle lang={lang} onChange={onLangChange} />
      <p style={{ fontSize: "0.68rem", color: "var(--clay)", textTransform: "uppercase", letterSpacing: "0.12em", marginBottom: "0.5rem" }}>
        {t.moduleEyebrow}
      </p>
      <h1 style={{ fontFamily: "'Fraunces', serif", fontSize: "2rem", fontWeight: 300, color: "var(--ink)", marginBottom: "0.25rem" }}>
        {t.title}
      </h1>
      <p style={{ fontSize: "0.88rem", color: "var(--hint)", marginBottom: "1.5rem", fontWeight: 300 }}>
        {t.subtitle}
      </p>
      {error && <p style={{ color: "var(--error)", fontSize: "0.8rem", marginBottom: "1rem" }}>⚠ {error}</p>}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginTop: "1.5rem" }}>
        {Object.keys(POS_META).map((pos) => {
          const meta = POS_META[pos];
          const words = wordsByPos[pos] ?? [];
          const hasWords = words.length > 0;
          return (
            <button key={pos} type="button" disabled={!hasWords} onClick={() => hasWords && onSelect(pos, words)} style={{
              textAlign: "left", padding: "1rem", borderRadius: 14,
              border: `1.5px solid ${hasWords ? meta.accent + "44" : "#e8e8e8"}`,
              background: hasWords ? meta.light : "#fafafa", opacity: hasWords ? 1 : 0.45,
            }}>
              <div style={{ fontSize: "1.3rem" }}>{meta.icon}</div>
              <div style={{ fontWeight: 700, color: meta.accent }}>{meta.label}</div>
              <div style={{ fontSize: "0.65rem", color: "#888" }}>{words.length} words</div>
              {hasWords && (
                <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 8 }}>
                  {words.slice(0, 6).map((w) => {
                    const e = normalizeWordEntry(w);
                    return (
                      <span key={e.id ?? e.word} style={{
                        fontSize: "0.58rem", padding: "2px 6px", borderRadius: 4,
                        background: "#fff", border: `1px solid ${meta.accent}33`, color: meta.accent,
                      }}>
                        {e.word} · L{e.augmentation_level}
                      </span>
                    );
                  })}
                </div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function SessionScreen({ pos, words, onComplete, onExit, lang }) {
  const t = COPY[lang];
  const meta = POS_META[pos] ?? POS_META.OTHER;
  const isReal = words.length > 0 && typeof words[0] === "object" && words[0].id != null;
  const wordQueue = useRef(words.map(normalizeWordEntry));

  useEffect(() => {
    wordQueue.current = words.map(normalizeWordEntry);
  }, [words]);

  const [idx, setIdx] = useState(0);
  const [hearts, setHearts] = useState(HEARTS_MAX);
  const [feedback, setFeedback] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [phase, setPhase] = useState("attempt1");
  const [missed, setMissed] = useState([]);
  const [wordsDone, setWordsDone] = useState(0);
  const sessionEndedRef = useRef(false);
  const submittingRef = useRef(false);
  const heartsRef = useRef(HEARTS_MAX);
  const idxRef = useRef(0);
  const phaseRef = useRef("attempt1");
  const missedRef = useRef([]);

  const currentList = phase === "attempt2" ? missed : wordQueue.current;
  const currentWord = currentList[idx] ?? null;
  const totalInPhase = currentList.length;
  const progressPct = totalInPhase > 0 ? Math.round((wordsDone / totalInPhase) * 100) : 0;

  const finishSession = useCallback(async () => {
    if (sessionEndedRef.current) return;
    sessionEndedRef.current = true;
    if (isReal) {
      const { data, error } = await endSession();
      const payload = data ? { ...data, classifier_results: data.classifier_results ?? data.classifier ?? [] } : {};
      onComplete(error ? {} : payload);
    } else onComplete({});
  }, [isReal, onComplete]);

  const handleRecording = async (blob) => {
    if (submittingRef.current || !currentWord) return;
    submittingRef.current = true;
    setSubmitting(true);
    setFeedback(null);

    const expectedWord = normalizeWordEntry(currentWord).word;
    let responseData = null;

    if (isReal) {
      const { data, error } = await submitAttempt(blob, lang);
      if (error) {
        setFeedback({ error });
        submittingRef.current = false;
        setSubmitting(false);
        return;
      }
      responseData = data;
      heartsRef.current = data?.hearts ?? data?.hearts_remaining ?? heartsRef.current;
      setHearts(heartsRef.current);

      const attemptFeedback = buildAttemptFeedback(responseData, expectedWord, false);
      setWordsDone((n) => n + 1);
      setFeedback(attemptFeedback);

      if (!attemptFeedback.correct && phaseRef.current === "attempt1") {
        missedRef.current = [...missedRef.current, currentWord];
        setMissed(missedRef.current);
      }

      const advance = () => {
        setFeedback(null);
        const curList = phaseRef.current === "attempt2" ? missedRef.current : wordQueue.current;
        const next = idxRef.current + 1;
        const nextState = responseData?.next_word_state;

        if (data?.session_over || next >= curList.length) {
          if (!data?.session_over && phaseRef.current === "attempt1" && missedRef.current.length > 0) {
            phaseRef.current = "attempt2";
            heartsRef.current = HEARTS_MAX;
            setPhase("attempt2");
            setHearts(HEARTS_MAX);
            idxRef.current = 0;
            setIdx(0);
            setWordsDone(0);
          } else {
            finishSession();
          }
        } else if (nextState && isReal) {
          const list = phaseRef.current === "attempt2" ? missedRef.current : wordQueue.current;
          const i = list.findIndex((w) => w.word === nextState.word);
          if (i >= 0) list[i] = { ...list[i], ...nextState };
          idxRef.current = i >= 0 ? i : next;
          setIdx(idxRef.current);
        } else {
          idxRef.current = next;
          setIdx(next);
        }
        submittingRef.current = false;
        setSubmitting(false);
      };

      setTimeout(advance, 1800);
      return;
    }

    const demoFeedback = buildAttemptFeedback(null, expectedWord, true);
    setWordsDone((n) => n + 1);
    setFeedback(demoFeedback);

    setTimeout(() => {
      setFeedback(null);
      const next = idxRef.current + 1;
      const curList = wordQueue.current;
      if (next >= curList.length) finishSession();
      else {
        idxRef.current = next;
        setIdx(next);
      }
      submittingRef.current = false;
      setSubmitting(false);
    }, 1800);
  };

  if (!currentWord) return null;
  const e = normalizeWordEntry(currentWord);
  const level = e.augmentation_level ?? 0;
  const gap = e.augmentation_gap ?? 0;

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
        <button
          type="button"
          onClick={onExit}
          style={{
            border: "1px solid var(--stone)",
            borderRadius: 999,
            background: "var(--white)",
            color: "var(--moss)",
            padding: "0.4rem 0.75rem",
            fontSize: "0.72rem",
            fontWeight: 700,
            cursor: "pointer",
          }}
        >
          Back
        </button>

        <Hearts count={hearts} />
        <div style={{ flex: 1, height: 6, background: "var(--sand)", borderRadius: 99, overflow: "hidden" }}>
          <div style={{ width: `${progressPct}%`, height: "100%", background: meta.accent, transition: "width 0.3s" }} />
        </div>
        <span style={{ fontSize: "0.72rem", color: "var(--hint)", minWidth: 48, textAlign: "right" }}>
          {wordsDone}/{totalInPhase}
        </span>
      </div>
      <p style={{ fontSize: "0.78rem", color: "var(--hint)", marginBottom: "0.5rem" }}>
        {meta.icon} {meta.label}
        {phase === "attempt2" && ` ${t.retryRound}`}
      </p>
      <div style={{
        textAlign: "center", padding: "2.5rem 1rem", borderRadius: 16,
        border: `1px solid ${feedback?.correct === true ? "#1a6b3c44" : feedback?.correct === false ? "#c0392b44" : "var(--stone)"}`,
        background: "var(--white)",
        minHeight: 220,
        transition: "border-color 0.2s",
      }}>
        <AugmentedWord word={e.word} level={level} />
        <div style={{ marginTop: 12, fontSize: "0.65rem", color: "var(--hint)", fontFamily: "monospace" }}>
          {AUG_LEVEL_LABELS[level] ?? "plain"} augmentation
          {gap !== 0 && ` · gap ${gap > 0 ? "+" : ""}${gap}`}
        </div>
        {feedback && !feedback.error && (
          <div style={{ marginTop: "1.25rem", paddingTop: "1rem", borderTop: "1px solid var(--sand)" }}>
            <p style={{ color: feedback.correct ? "#1a6b3c" : "#c0392b", fontWeight: 500, marginBottom: 8 }}>
              {feedback.correct ? t.greatJob : t.notQuite}
            </p>
            <p style={{ fontSize: "0.88rem", color: "var(--muted)", lineHeight: 1.5 }}>
              {t.youSaid}{" "}
              <em style={{ color: "var(--ink)" }}>
                "{feedback.transcript?.trim() ? feedback.transcript : t.noSpeech}"
              </em>
            </p>
            <p style={{ fontSize: "0.8rem", color: "var(--hint)", marginTop: 6 }}>
              {t.matchAccuracy}{" "}
              <strong style={{ color: "var(--ink)" }}>{Math.round(feedback.match_accuracy ?? 0)}%</strong>
              {feedback.confidence != null && (
                <span> · {t.sttConfidence} {Math.round(feedback.confidence * 100)}%</span>
              )}
            </p>
          </div>
        )}
        {feedback?.error && (
          <p style={{ color: "var(--error)", marginTop: 12, fontSize: "0.85rem" }}>⚠ {feedback.error}</p>
        )}
      </div>
      <div style={{ display: "flex", justifyContent: "center", margin: "2rem 0" }}>
        <RecordButton lang={lang} onRecordingComplete={handleRecording} disabled={submitting || !!feedback} />
      </div>
      <button type="button" onClick={onExit} style={{ width: "100%", background: "none", border: "none", color: "var(--hint)" }}>
        {t.endEarly}
      </button>
    </div>
  );
}

function ResultsScreen({ result, pos, onBack, lang }) {
  const t = COPY[lang];
  const meta = POS_META[pos] ?? POS_META.OTHER;
  const {
    completed = false,
    hearts_remaining = 0,
    escalated = [],
    regressed = [],
    classifier_results = [],
    rr_applied = [],
    rr_correction_summary = {},
    words_attempted = 0,
  } = result ?? {};
  const wordCount = words_attempted || classifier_results.length;
  const rr = rr_correction_summary;

  return (
    <div>
      <div style={{
        textAlign: "center", padding: "1.75rem 1.25rem", marginBottom: "1.5rem",
        borderRadius: 16, background: completed ? meta.light : "var(--sand)",
        border: `1.5px solid ${meta.accent}33`,
      }}>
        <span style={{ fontSize: "2.25rem", display: "block", marginBottom: "0.5rem" }}>{completed ? "🎉" : "💪"}</span>
        <h2 style={{ fontFamily: "'Fraunces', serif", fontWeight: 300, fontSize: "1.75rem", color: "var(--ink)", marginBottom: "0.35rem" }}>
          {completed ? t.sessionComplete : t.sessionEnded}
        </h2>
        <p style={{ fontSize: "0.85rem", color: "var(--hint)", fontWeight: 300 }}>
          {meta.icon} {meta.label} · {wordCount} {t.wordsAssessed}
        </p>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, marginBottom: "1.5rem" }}>
        {[
          { n: hearts_remaining, label: t.heartsLeft, accent: "#c0392b" },
          { n: escalated.length, label: t.escalated, accent: "#1a6b3c" },
          { n: regressed.length, label: t.regressed, accent: meta.accent },
        ].map(({ n, label, accent }) => (
          <div key={label} style={{ textAlign: "center", padding: "1rem 0.5rem", borderRadius: 14, background: "var(--white)", border: "1px solid var(--stone)" }}>
            <div style={{ fontSize: "1.5rem", fontWeight: 600, color: accent, fontFamily: "'Fraunces', serif" }}>{n}</div>
            <div style={{ fontSize: "0.62rem", color: "var(--hint)", marginTop: 4, textTransform: "uppercase", letterSpacing: "0.06em" }}>{label}</div>
          </div>
        ))}
      </div>
      {(rr.under_augmented != null || rr.correct != null) && (
        <div style={{ padding: "1rem", borderRadius: 14, background: "var(--white)", border: "1px solid var(--stone)", marginBottom: "1.25rem" }}>
          <p style={{ fontSize: "0.68rem", color: "var(--clay)", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: "0.75rem" }}>{t.rrSection}</p>
          {[
            { key: "under_augmented", label: t.underAug, color: "#1a6b3c" },
            { key: "correct", label: t.rrCorrect, color: "#5C6E42" },
            { key: "over_augmented", label: t.overAug, color: "#B85C38" },
          ].map(({ key, label, color }) => (
            <div key={key} style={{ display: "flex", justifyContent: "space-between", padding: "0.4rem 0", borderBottom: "1px solid var(--sand)" }}>
              <span style={{ fontSize: "0.82rem", color: "var(--muted)" }}>{label}</span>
              <span style={{ fontSize: "0.9rem", fontWeight: 600, color }}>{rr[key] ?? 0}</span>
            </div>
          ))}
        </div>
      )}
      {rr_applied.length > 0 && (
        <p style={{ fontSize: "0.82rem", color: "#1a6b3c", padding: "0.65rem 0.9rem", background: "#e8f5ee", borderRadius: 10, marginBottom: "1.25rem", border: "1px solid #1a6b3c33" }}>
          {t.rrApplied}: <strong>{rr_applied.join(", ")}</strong>
        </p>
      )}
      {classifier_results.length > 0 && (
        <div style={{ marginBottom: "1.5rem" }}>
          <p style={{ fontSize: "0.68rem", color: "var(--clay)", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: "0.65rem" }}>{t.wordBreakdown}</p>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {classifier_results.map((r) => {
              const rec = RECOMMENDATION_STYLE[r.recommendation] ?? RECOMMENDATION_STYLE.keep;
              return (
                <div key={r.word} style={{ display: "flex", alignItems: "center", gap: 10, padding: "0.75rem 1rem", borderRadius: 12, background: rec.light, border: `1px solid ${rec.accent}33` }}>
                  <span style={{ width: 28, height: 28, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", background: "var(--white)", color: rec.accent, fontWeight: 700 }}>{rec.icon}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 600, color: "var(--ink)", fontSize: "0.95rem" }}>{r.word}</div>
                    <div style={{ fontSize: "0.78rem", color: rec.accent, marginTop: 2 }}>
                      {recommendationLabel(r, lang)}
                      {r.augmentation_level_after != null && (
                        <span style={{ color: "var(--hint)" }}> {t.nowLevel(r.augmentation_level_after, r.aug_tier_label_after ?? "")}</span>
                      )}
                    </div>
                  </div>
                  {r.confidence != null && <span style={{ fontSize: "0.72rem", color: "var(--hint)" }}>{Math.round(r.confidence * 100)}%</span>}
                </div>
              );
            })}
          </div>
        </div>
      )}
      <button type="button" onClick={onBack} style={{ marginTop: "0.25rem", width: "100%", padding: "0.95rem", borderRadius: 12, border: "none", background: "var(--clay)", color: "var(--white)", fontSize: "0.9rem", fontWeight: 500, cursor: "pointer", boxShadow: "0 2px 8px rgba(184,92,56,0.25)" }}>
        {t.backToTypes}
      </button>
    </div>
  );
}

export default function WordProficiency() {
  const [screen, setScreen] = useState("select");
  const [lang, setLang] = useState(() => localStorage.getItem("wp_lang") || "en");
  const [wordsByPos, setWordsByPos] = useState({});
  const [loadError, setLoadError] = useState(null);
  const [activePos, setActivePos] = useState(null);
  const [sessionWords, setSessionWords] = useState([]);
  const [endResult, setEndResult] = useState(null);

  const [reviewWords, setReviewWords] = useState(() => getDifficultWords());

  const importedReviewKeyRef = useRef("");

  const seedForLang = (language) => (language === "fil" ? SEED_WORDS_FIL : SEED_WORDS);

  const handleLangChange = (next) => {
    setLang(next);
    localStorage.setItem("wp_lang", next);
  };

  const loadWords = useCallback(async () => {
    const seeds = seedForLang(lang);
    const { data, error } = await getWords({ language: lang });
    if (error) {
      setLoadError(error);
      const seeded = {};
      for (const [pos, list] of Object.entries(seeds)) seeded[pos] = list;
      setWordsByPos(seeded);
      return;
    }
    let list = Array.isArray(data) ? data : [];
    list = list.filter((ws) => wordLanguage(ws) === lang);
    if (list.length === 0) {
      const seeded = {};
      for (const [pos, list2] of Object.entries(seeds)) seeded[pos] = list2;
      setWordsByPos(seeded);
      return;
    }
    const otherApi = list.filter((ws) => apiPosTag(ws) === "OTHER").length;
    if (otherApi > list.length * 0.25) {
      await syncPosTags();
      const refreshed = await getWords({ language: lang });
      if (!refreshed.error && Array.isArray(refreshed.data)) list = refreshed.data;
    }
    const byPos = {};
    for (const ws of list) {
      const p = resolvePosTag(ws);
      if (!byPos[p]) byPos[p] = [];
      byPos[p].push(ws);
    }
    setWordsByPos(byPos);
  }, [lang]);

  useEffect(() => { loadWords(); }, [loadWords]);
  useEffect(() => subscribeDifficultWords(setReviewWords), []);

  useEffect(() => {
    const words = reviewWords
      .map((item) => String(item.word || "").trim().toLowerCase())
      .filter(Boolean);
    const uniqueWords = [...new Set(words)];
    const importKey = uniqueWords.join("|");
    if (!importKey || importedReviewKeyRef.current === importKey) return;

    importedReviewKeyRef.current = importKey;
    let cancelled = false;

    ;(async () => {
      const payload = uniqueWords.map((word) => ({
        word,
        rr_augmentation_level: 1,
        language: lang,
      }));
      const { data, error } = await importWords(payload);
      if (cancelled || error) return;
      if ((data?.created || 0) > 0) {
        await loadWords();
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [reviewWords, lang, loadWords]);

  const handlePracticeReviewWords = async () => {
    const reviewSet = new Set(
      reviewWords.map((item) => String(item.word || "").toLowerCase()).filter(Boolean)
    );
    if (!reviewSet.size) return;

    const availableWords = Object.values(wordsByPos)
      .flat()
      .map(normalizeWordEntry)
      .filter((entry) => entry.id != null && reviewSet.has(String(entry.word).toLowerCase()));

    if (!availableWords.length) {
      setLoadError("Review words are still being classified. Please try again in a moment.");
      await loadWords();
      return;
    }

    const sessionSize = Math.min(10, availableWords.length);
    const wordIds = availableWords.map((entry) => entry.id);
    const { data, error } = await startSession(sessionSize, null, wordIds);

    if (error) {
      setLoadError(error);
      return;
    }

    if (data?.words?.length) {
      setActivePos("OTHER");
      setSessionWords(data.words.map(normalizeWordEntry));
      setScreen("session");
    }
  };

  const handleRemoveReviewWord = (word) => {
    setReviewWords(removeDifficultWord(word));
  };

  const handleSelectPos = async (pos, words) => {
    if (!words?.length) return;
    const isReal = typeof words[0] === "object" && words[0].id != null;
    if (isReal) {
      const sessionSize = Math.min(10, words.length);
      const wordIds = words.map((w) => w.id).filter((id) => id != null);
      const { data, error } = await startSession(sessionSize, pos, wordIds);
      if (error) { setLoadError(error); return; }
      if (data?.words?.length) {
        setActivePos(pos);
        setSessionWords(data.words.map(normalizeWordEntry));
        setScreen("session");
        return;
      }
      setLoadError("No words available for this category.");
      return;
    }
    setActivePos(pos);
    setSessionWords(words.map(normalizeWordEntry));
    setScreen("session");
  };

  const handleSessionComplete = (result) => {
    setWordsByPos((prev) => applySessionLevelsToWordsByPos(prev, result));
    setEndResult(result);
    setScreen("results");
  };

  const handleBack = async () => {
    setEndResult(null);
    setActivePos(null);
    setSessionWords([]);
    setScreen("select");
    await loadWords();
  };

  if (screen === "session") {
    return (
      <SessionScreen
        pos={activePos}
        words={sessionWords}
        lang={lang}
        onComplete={handleSessionComplete}
        onExit={handleBack}
      />
    );
  }
  if (screen === "results") {
    return <ResultsScreen result={endResult} pos={activePos} lang={lang} onBack={handleBack} />;
  }
  return (
    <PosSelectionScreen
      wordsByPos={wordsByPos}
      onSelect={handleSelectPos}
      error={loadError}
      lang={lang}
      onLangChange={handleLangChange}
      reviewWords={reviewWords}
      onPracticeReviewWords={handlePracticeReviewWords}
      onRemoveReviewWord={handleRemoveReviewWord}
    />
  );
}
