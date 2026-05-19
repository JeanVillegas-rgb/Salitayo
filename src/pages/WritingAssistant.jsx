import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Sidebar from "../components/Sidebar";

import {
  getPassages,
  getPassageById,
  analyzeWriting,
  updateFlagged,
  transcribeAudio,
} from "../services/api";

/* ── inline styles ─────────────────────────────────────────────────────── */
const S = {
  /* topbar */
  topbar: {
    padding: "1.1rem 2.5rem",
    display: "flex",
    alignItems: "center",
    gap: "1rem",
    borderBottom: "1px solid var(--sand)",
    background: "rgba(247,242,234,0.85)",
    backdropFilter: "blur(8px)",
    position: "sticky",
    top: 0,
    zIndex: 10,
  },
  breadcrumb: {
    display: "flex",
    alignItems: "center",
    gap: "0.5rem",
    fontSize: "0.78rem",
    color: "var(--hint)",
  },
  crumbActive: { color: "var(--ink)", fontWeight: 500 },
  stepPills: { display: "flex", alignItems: "center", gap: "0.375rem", marginLeft: "auto" },

  /* content wrapper */
  content: {
    flex: 1,
    padding: "2.75rem 3rem",
    maxWidth: 760,
  },

  /* typography */
  eyebrow: {
    fontSize: "0.68rem",
    color: "var(--clay)",
    textTransform: "uppercase",
    letterSpacing: "0.12em",
    fontWeight: 500,
    marginBottom: "0.4rem",
  },
  h1: {
    fontFamily: "'Fraunces', serif",
    fontSize: "2rem",
    fontWeight: 300,
    color: "var(--ink)",
    lineHeight: 1.2,
    marginBottom: "0.6rem",
  },
  desc: {
    fontSize: "0.88rem",
    color: "var(--muted)",
    lineHeight: 1.75,
    fontWeight: 300,
    maxWidth: 520,
    marginBottom: "2.25rem",
  },

  /* back btn */
  backBtn: {
    display: "inline-flex",
    alignItems: "center",
    gap: "0.4rem",
    fontSize: "0.78rem",
    color: "var(--muted)",
    background: "none",
    border: "none",
    cursor: "pointer",
    padding: "0.3rem 0",
    marginBottom: "1.75rem",
    fontFamily: "'DM Sans', sans-serif",
    transition: "color 0.2s",
  },

  /* mode cards */
  modeGrid: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "2rem" },
  modeCard: {
    background: "white",
    border: "1.5px solid var(--stone)",
    borderRadius: 16,
    padding: "1.75rem 1.5rem",
    cursor: "pointer",
    textAlign: "left",
    display: "flex",
    flexDirection: "column",
    gap: "0.5rem",
    fontFamily: "'DM Sans', sans-serif",
    transition: "all 0.2s",
  },
  modeIcon: { fontSize: "1.4rem", marginBottom: "0.125rem" },
  modeTitle: { fontSize: "0.95rem", fontWeight: 500, color: "var(--ink)" },
  modeSub: { fontSize: "0.78rem", color: "var(--hint)", lineHeight: 1.6, fontWeight: 300 },

  /* section label */
  sectionLabel: {
    fontSize: "0.7rem",
    textTransform: "uppercase",
    letterSpacing: "0.1em",
    color: "var(--hint)",
    fontWeight: 500,
    marginBottom: "0.625rem",
  },

  /* select */
  select: {
    width: "100%",
    padding: "11px 14px",
    borderRadius: 12,
    border: "1.5px solid var(--stone)",
    background: "white",
    fontFamily: "'DM Sans', sans-serif",
    fontSize: "0.9rem",
    color: "var(--ink)",
    outline: "none",
    cursor: "pointer",
    marginBottom: "1rem",
    transition: "border-color 0.2s",
  },

  /* preview box */
  previewBox: {
    background: "var(--sand)",
    borderRadius: 12,
    padding: "1.125rem 1.375rem",
    fontSize: "0.85rem",
    color: "var(--muted)",
    lineHeight: 1.75,
    marginBottom: "1.5rem",
    border: "1px solid var(--stone)",
  },

  /* buttons */
  btnPrimary: {
    padding: "11px 1.75rem",
    borderRadius: 100,
    border: "none",
    background: "var(--clay)",
    color: "white",
    fontFamily: "'DM Sans', sans-serif",
    fontSize: "0.88rem",
    fontWeight: 400,
    cursor: "pointer",
    transition: "background 0.2s",
  },
  btnGhost: {
    padding: "10px 1.5rem",
    borderRadius: 100,
    border: "1.5px solid var(--stone)",
    background: "transparent",
    color: "var(--muted)",
    fontFamily: "'DM Sans', sans-serif",
    fontSize: "0.88rem",
    cursor: "pointer",
    transition: "all 0.2s",
  },
  btnAnalyze: {
    width: "100%",
    padding: "13px",
    borderRadius: 100,
    border: "none",
    background: "var(--moss)",
    color: "white",
    fontFamily: "'DM Sans', sans-serif",
    fontSize: "0.93rem",
    fontWeight: 400,
    cursor: "pointer",
    transition: "background 0.2s",
    marginBottom: "1rem",
    letterSpacing: "0.01em",
  },
  btnRecord: {
    padding: "9px 1.25rem",
    borderRadius: 100,
    border: "1.5px solid var(--sage)",
    background: "rgba(92,110,66,0.06)",
    color: "var(--fern)",
    fontFamily: "'DM Sans', sans-serif",
    fontSize: "0.83rem",
    cursor: "pointer",
    transition: "all 0.2s",
  },
  btnStop: {
    padding: "9px 1.25rem",
    borderRadius: 100,
    border: "1.5px solid var(--error)",
    background: "rgba(184,50,50,0.06)",
    color: "var(--error)",
    fontFamily: "'DM Sans', sans-serif",
    fontSize: "0.83rem",
    cursor: "pointer",
  },
  btnSuccess: {
    padding: "11px 1.5rem",
    borderRadius: 100,
    border: "none",
    background: "var(--clay)",
    color: "white",
    fontFamily: "'DM Sans', sans-serif",
    fontSize: "0.88rem",
    cursor: "pointer",
  },
  btnKeepOriginal: {
    padding: "10px 1.5rem",
    borderRadius: 100,
    border: "1.5px solid var(--stone)",
    background: "transparent",
    color: "var(--muted)",
    fontFamily: "'DM Sans', sans-serif",
    fontSize: "0.88rem",
    cursor: "pointer",
  },

  /* language */
  langRow: { display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "1.375rem", flexWrap: "wrap" },
  langBtnBase: {
    padding: "8px 1.25rem",
    borderRadius: 100,
    border: "1.5px solid var(--stone)",
    background: "white",
    fontFamily: "'DM Sans', sans-serif",
    fontSize: "0.83rem",
    color: "var(--muted)",
    cursor: "pointer",
    transition: "all 0.2s",
  },
  langBtnActive: {
    padding: "8px 1.25rem",
    borderRadius: 100,
    border: "1.5px solid var(--fern)",
    background: "rgba(92,110,66,0.07)",
    fontFamily: "'DM Sans', sans-serif",
    fontSize: "0.83rem",
    color: "var(--fern)",
    fontWeight: 500,
    cursor: "pointer",
  },

  /* ref banner */
  refBanner: {
    display: "inline-flex",
    alignItems: "center",
    gap: "0.5rem",
    background: "var(--sand)",
    border: "1px solid var(--stone)",
    borderRadius: 10,
    padding: "0.45rem 1rem",
    fontSize: "0.8rem",
    color: "var(--muted)",
    marginBottom: "1.375rem",
  },

  /* textarea */
  textarea: {
    width: "100%",
    minHeight: 180,
    padding: "1.125rem",
    borderRadius: 14,
    border: "1.5px solid var(--stone)",
    background: "white",
    fontFamily: "'DM Sans', sans-serif",
    fontSize: "0.93rem",
    color: "var(--ink)",
    lineHeight: 1.75,
    resize: "vertical",
    outline: "none",
    transition: "border-color 0.2s",
    marginBottom: "0.875rem",
  },

  /* speech */
  speechRow: { display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1.125rem", flexWrap: "wrap" },
  recDot: { display: "inline-flex", alignItems: "center", gap: "0.375rem", fontSize: "0.78rem", color: "var(--error)" },

  /* results */
  resultsHeader: { display: "flex", alignItems: "baseline", gap: "1.25rem", marginBottom: "1.375rem", flexWrap: "wrap" },
  resultsTitle: { fontFamily: "'Fraunces', serif", fontSize: "1.3rem", fontWeight: 300 },
  countChips: { display: "flex", gap: "0.5rem" },
  chipIssues: {
    display: "flex", alignItems: "center", gap: "0.375rem",
    padding: "4px 12px", borderRadius: 100, fontSize: "0.78rem",
    background: "rgba(184,92,56,0.1)", color: "var(--clay)", border: "1px solid rgba(184,92,56,0.2)",
  },
  chipResolved: {
    display: "flex", alignItems: "center", gap: "0.375rem",
    padding: "4px 12px", borderRadius: 100, fontSize: "0.78rem",
    background: "rgba(92,110,66,0.1)", color: "var(--fern)", border: "1px solid rgba(92,110,66,0.2)",
  },
  chipNum: { fontWeight: 600, fontSize: "0.88rem" },

  topicChip: {
    display: "inline-flex", alignItems: "center", gap: "0.5rem",
    padding: "5px 14px", borderRadius: 100,
    background: "var(--sand)", border: "1px solid var(--stone)",
    fontSize: "0.78rem", color: "var(--muted)", marginBottom: "1.125rem",
  },

  /* issue card */
  issueCard: {
    background: "white",
    borderRadius: 14,
    padding: "1.25rem 1.5rem",
    marginBottom: "0.875rem",
    border: "1.5px solid var(--stone)",
    transition: "border-color 0.2s",
  },
  cardBadges: { display: "flex", gap: "0.5rem", marginBottom: "0.875rem" },
  badgeType: {
    padding: "3px 10px", borderRadius: 100, fontSize: "0.68rem", fontWeight: 500,
    background: "var(--sand)", color: "var(--muted)", border: "1px solid var(--stone)",
    textTransform: "uppercase", letterSpacing: "0.06em",
  },

  /* resolved card */
  resolvedCard: {
    display: "flex", alignItems: "center", justifyContent: "space-between",
    background: "rgba(92,110,66,0.05)", border: "1px solid rgba(92,110,66,0.2)",
    borderRadius: 12, padding: "0.875rem 1.25rem",
    marginBottom: "0.625rem", fontSize: "0.85rem", color: "var(--muted)",
  },

  /* no issues */
  noIssues: {
    background: "rgba(92,110,66,0.07)", border: "1px solid rgba(92,110,66,0.2)",
    borderRadius: 12, padding: "1.25rem 1.5rem", fontSize: "0.88rem", color: "var(--fern)",
  },

  /* bottom actions */
  bottomRow: {
    display: "flex", gap: "0.75rem", marginTop: "2rem",
    paddingTop: "1.5rem", borderTop: "1px solid var(--sand)", flexWrap: "wrap",
  },

  /* popup */
  overlay: {
    position: "fixed", inset: 0, background: "rgba(28,26,20,0.5)",
    backdropFilter: "blur(4px)", display: "flex",
    alignItems: "center", justifyContent: "center", zIndex: 200, padding: "1.5rem",
  },
  popup: {
    background: "white", borderRadius: 20, padding: "2rem",
    maxWidth: 500, width: "100%",
    boxShadow: "0 24px 60px rgba(28,26,20,0.18)",
  },
  popupTitle: { fontFamily: "'Fraunces', serif", fontSize: "1.2rem", fontWeight: 300, marginBottom: "0.3rem" },
  popupSub: { fontSize: "0.82rem", color: "var(--muted)", marginBottom: "1.5rem", fontWeight: 300 },
  compareBlock: (variant) => ({
    borderRadius: 12,
    padding: "1.1rem 1.25rem",
    marginBottom: "0.875rem",
    background: variant === "before" ? "rgba(184,92,56,0.06)" : "rgba(92,110,66,0.06)",
    border: variant === "before" ? "1px solid rgba(184,92,56,0.2)" : "1px solid rgba(92,110,66,0.2)",
  }),
  compareLabel: (variant) => ({
    fontSize: "0.68rem",
    textTransform: "uppercase",
    letterSpacing: "0.1em",
    fontWeight: 500,
    marginBottom: "0.375rem",
    color: variant === "before" ? "var(--clay)" : "var(--fern)",
  }),
  compareText: { fontSize: "0.88rem", lineHeight: 1.75, color: "var(--ink)" },
  popupBtns: { display: "flex", gap: "0.625rem" },

  /* no passages */
  noPassages: { textAlign: "center", padding: "2.5rem" },

  /* open mode banner */
  openBanner: {
    display: "inline-flex", alignItems: "center", gap: "0.5rem",
    padding: "0.45rem 1rem", borderRadius: 10,
    background: "rgba(92,110,66,0.08)", border: "1px solid rgba(92,110,66,0.2)",
    fontSize: "0.8rem", color: "var(--fern)", marginBottom: "1.375rem",
  },

  /* error */
  error: { fontSize: "0.82rem", color: "var(--error)", marginBottom: "0.875rem" },
  transcribeErr: { fontSize: "0.78rem", color: "var(--error)" },
  transcribeInfo: { fontSize: "0.78rem", color: "var(--hint)" },
};

/* ── step dot ──────────────────────────────────────────────────────────── */
function StepDot({ state }) {
  const base = { width: 8, height: 8, borderRadius: "50%", transition: "all 0.3s" };
  const color =
    state === "active" ? "var(--clay)"
    : state === "done"   ? "var(--sage)"
    : "var(--stone)";
  return <span style={{ ...base, background: color, display: "inline-block" }} />;
}

function StepConnector() {
  return <span style={{ width: 20, height: 1, background: "var(--stone)", display: "inline-block" }} />;
}

/* ── highlight helper ──────────────────────────────────────────────────── */
function highlight(sentence, word, bg) {
  const parts = sentence.split(new RegExp(`(${word})`, "gi"));
  return parts.map((part, i) =>
    part.toLowerCase() === word.toLowerCase() ? (
      <mark key={i} style={{ background: bg, padding: "0 3px", borderRadius: 4, fontWeight: 500 }}>
        {part}
      </mark>
    ) : part
  );
}

/* ── severity helpers ──────────────────────────────────────────────────── */
const severityColor = (s) =>
  s === "significant" ? "var(--error)"
  : s === "moderate"  ? "#C07A1A"
  : "var(--fern)";

const severityLabel = (s) =>
  s === "significant" ? "Significant"
  : s === "moderate"  ? "Moderate"
  : "Gentle";

const typeLabel = (t) =>
  t === "spelling"     ? "Spelling"
  : t === "grammar"   ? "Grammar"
  : t === "language_mix" ? "Language Mix"
  : "Out of Place";

/* ── component ─────────────────────────────────────────────────────────── */
export default function WritingAssistant() {
  const navigate = useNavigate();

  const [step, setStep] = useState(1);
  const [mode, setMode] = useState(null);

  const [passages, setPassages] = useState([]);
  const [selectedPassageId, setSelectedPassageId] = useState("");
  const [selectedPassageContent, setSelectedPassageContent] = useState("");
  const [selectedPassageTitle, setSelectedPassageTitle] = useState("");

  const [userText, setUserText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [language, setLanguage] = useState("english");

  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [mediaRecorder, setMediaRecorder] = useState(null);
  const [transcribeError, setTranscribeError] = useState(null);

  const [results, setResults] = useState(null);
  const [flaggedIds, setFlaggedIds] = useState([]);
  const [topic, setTopic] = useState(null);
  const [resolved, setResolved] = useState({});
  const [dismissed, setDismissed] = useState({});
  const [comparison, setComparison] = useState(null);

  useEffect(() => {
    if (step === 2 && mode === "existing_text") {
      getPassages()
        .then((res) => setPassages(res.data.passages))
        .catch(console.error);
    }
  }, [step, mode]);

  useEffect(() => {
    if (selectedPassageId) {
      getPassageById(selectedPassageId)
        .then((res) => {
          setSelectedPassageContent(res.data.content);
          setSelectedPassageTitle(res.data.title);
        })
        .catch(console.error);
    }
  }, [selectedPassageId]);

  const handleModeSelect = (m) => {
    setMode(m);
    setStep(m === "existing_text" ? 2 : 3);
  };

  useEffect(() => {
  const importedText = sessionStorage.getItem("importedText");

  if (importedText) {
    setUserText(importedText);
    setMode("open_topic");
    setStep(3);

    // optional: clear after use
    sessionStorage.removeItem("importedText");
    sessionStorage.removeItem("importedFileName");
  }
  }, []);

  const handleAnalyze = async () => {
    setLoading(true);
    setError(null);
    setResults(null);
    setResolved({});
    setDismissed({});
    setFlaggedIds([]);
    setTopic(null);

    try {
      const payload = { text: userText, mode, language };
      if (mode === "existing_text") payload.passage_id = selectedPassageId;

      const res = await analyzeWriting(payload);
      const d = res.data.result;

      setResults(d.flagged_words);
      setFlaggedIds(d.flagged_ids || []);
      if (d.identified_topic) setTopic(d.identified_topic);
    } catch {
      setError("Something went wrong. Check if Django is running.");
    }

    setLoading(false);
  };

  const handleSuggestionClick = (idx, suggestion) => {
    const original = results[idx].original;
    const sentences = userText.match(/[^.!?]+[.!?]+/g) || [userText];

    const originalSentence =
      sentences.find((s) => s.toLowerCase().includes(original.toLowerCase())) || userText;

    const changedSentence = originalSentence.replace(
      new RegExp(original, "gi"),
      suggestion.replacement
    );

    setComparison({
      itemIndex: idx,
      original,
      suggestion,
      originalSentence: originalSentence.trim(),
      changedSentence: changedSentence.trim(),
    });
  };

  const handleApply = async () => {
    const { itemIndex, original, suggestion } = comparison;

    setUserText((t) => t.replace(new RegExp(original, "gi"), suggestion.replacement));
    setResolved((p) => ({ ...p, [itemIndex]: { replacement: suggestion.replacement, original } }));

    if (flaggedIds[itemIndex]) {
      await updateFlagged({
        flagged_id: flaggedIds[itemIndex],
        action: "apply",
        applied_suggestion: suggestion.replacement,
      }).catch(console.error);
    }

    setComparison(null);
  };

  const handleUndo = async (idx) => {
    const { replacement, original } = resolved[idx];

    setUserText((t) => t.replace(new RegExp(replacement, "gi"), original));
    setResolved((p) => { const u = { ...p }; delete u[idx]; return u; });

    if (flaggedIds[idx]) {
      await updateFlagged({ flagged_id: flaggedIds[idx], action: "undo" }).catch(console.error);
    }
  };

  const handleDismiss = async (idx) => {
    setDismissed((p) => ({ ...p, [idx]: true }));

    if (flaggedIds[idx]) {
      await updateFlagged({ flagged_id: flaggedIds[idx], action: "dismiss" }).catch(console.error);
    }
  };

  const startRecording = async () => {
    setTranscribeError(null);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      const chunks = [];

      recorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };

      recorder.onstop = async () => {
        setTranscribing(true);
        const blob = new Blob(chunks, { type: "audio/webm" });
        const formData = new FormData();
        formData.append("audio", blob, "recording.webm");

        try {
          const res = await transcribeAudio(formData);
          setUserText((p) => p ? p + " " + res.data.transcription : res.data.transcription);
        } catch {
          setTranscribeError("Transcription failed. Please try again.");
        }

        setTranscribing(false);
        stream.getTracks().forEach((t) => t.stop());
      };

      recorder.start();
      setMediaRecorder(recorder);
      setRecording(true);
    } catch {
      setTranscribeError("Microphone access denied.");
    }
  };

  const stopRecording = () => {
    if (mediaRecorder) {
      mediaRecorder.stop();
      setRecording(false);
      setMediaRecorder(null);
    }
  };

  const resetAll = () => {
    setStep(1);
    setMode(null);
    setLanguage("english");
    setUserText("");
    setResults(null);
    setResolved({});
    setDismissed({});
    setFlaggedIds([]);
    setTopic(null);
    setSelectedPassageId("");
    setSelectedPassageContent("");
    setSelectedPassageTitle("");
  };

  const onBack = () => {
    if (step === 1) { navigate("/home"); return; }
    setStep(mode === "existing_text" ? 2 : 1);
    setResults(null);
  };

  const resolvedCount = Object.keys(resolved).length;
  const activeCount = results
    ? results.filter((_, i) => !dismissed[i] && !resolved[i]).length
    : 0;

  /* step indicator state */
  const stepState = (n) =>
    n < step ? "done" : n === step ? "active" : "idle";

  return (
    <div className="app-layout">
      <Sidebar />

      <div className="app-main">

        {/* ── Comparison popup ── */}
        {comparison && (
          <div style={S.overlay}>
            <div style={S.popup}>
              <p style={S.popupTitle}>Compare Changes</p>
              <p style={S.popupSub}>See how your sentence looks before and after — you decide.</p>

              <div style={S.compareBlock("before")}>
                <p style={S.compareLabel("before")}>Before</p>
                <p style={S.compareText}>
                  {highlight(comparison.originalSentence, comparison.original, "#fadbd8")}
                </p>
              </div>

              <div style={S.compareBlock("after")}>
                <p style={S.compareLabel("after")}>After</p>
                <p style={S.compareText}>
                  {highlight(comparison.changedSentence, comparison.suggestion.replacement, "#d5f5e3")}
                </p>
              </div>

              <p style={{ fontSize: "0.8rem", color: "var(--muted)", marginBottom: "1.25rem" }}>
                <strong>Meaning similarity:</strong> {comparison.suggestion.similarity_score}%
              </p>

              <div style={S.popupBtns}>
                <button style={S.btnSuccess} onClick={handleApply}>✓ Apply Change</button>
                <button style={S.btnKeepOriginal} onClick={() => setComparison(null)}>Keep Original</button>
              </div>
            </div>
          </div>
        )}

        {/* ── Sticky topbar ── */}
        <div style={S.topbar}>
          <div style={S.breadcrumb}>
            <span>SALITAyo</span>
            <span style={{ color: "var(--stone)" }}>›</span>
            <span style={S.crumbActive}>Writing Assistant</span>
          </div>
          <div style={S.stepPills}>
            <StepDot state={stepState(1)} />
            <StepConnector />
            <StepDot state={stepState(2)} />
            <StepConnector />
            <StepDot state={stepState(3)} />
          </div>
        </div>

        {/* ── Page content ── */}
        <div style={S.content}>

          {/* ═══ SCREEN 1 — Mode select ═══ */}
          {step === 1 && (
            <>
              <button style={S.backBtn} onClick={onBack}>← Back to Home</button>

              <p style={S.eyebrow}>Step 1 of 3</p>
              <h1 style={S.h1}>What are you <em style={{ fontStyle: "italic" }}>writing</em> for today?</h1>
              <p style={S.desc}>
                Choose your mode. SALITAyo will review your writing and gently highlight areas
                you might want to improve — the final call is always yours.
              </p>

              <div style={S.modeGrid}>
                <button
                  style={S.modeCard}
                  onClick={() => handleModeSelect("existing_text")}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = "var(--clay)";
                    e.currentTarget.style.boxShadow = "0 4px 20px rgba(184,92,56,0.1)";
                    e.currentTarget.style.transform = "translateY(-1px)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = "var(--stone)";
                    e.currentTarget.style.boxShadow = "none";
                    e.currentTarget.style.transform = "none";
                  }}
                >
                  <span style={S.modeIcon}>📄</span>
                  <span style={S.modeTitle}>From an Existing Import</span>
                  <span style={S.modeSub}>Writing about something you've already read in SALITAyo</span>
                </button>

                <button
                  style={S.modeCard}
                  onClick={() => handleModeSelect("open_topic")}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = "var(--clay)";
                    e.currentTarget.style.boxShadow = "0 4px 20px rgba(184,92,56,0.1)";
                    e.currentTarget.style.transform = "translateY(-1px)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = "var(--stone)";
                    e.currentTarget.style.boxShadow = "none";
                    e.currentTarget.style.transform = "none";
                  }}
                >
                  <span style={S.modeIcon}>✏️</span>
                  <span style={S.modeTitle}>Open Topic</span>
                  <span style={S.modeSub}>Writing freely about any topic of your choice</span>
                </button>
              </div>
            </>
          )}

          {/* ═══ SCREEN 2 — Import selection ═══ */}
          {step === 2 && mode === "existing_text" && (
            <>
              <button style={S.backBtn} onClick={() => setStep(1)}>← Back</button>

              <p style={S.eyebrow}>Step 2 of 3</p>
              <h1 style={S.h1}>Select a <em style={{ fontStyle: "italic" }}>reference</em> passage.</h1>
              <p style={S.desc}>
                Choose from your saved imports. SALITAyo will use this as context when reviewing your writing.
              </p>

              {passages.length === 0 ? (
                <div style={S.noPassages}>
                  <p style={{ color: "var(--muted)", fontSize: "0.88rem", marginBottom: "1rem" }}>
                    You have no saved passages yet.
                  </p>
                  <button style={S.btnPrimary} onClick={() => navigate("/home")}>
                    Go to My Imports →
                  </button>
                </div>
              ) : (
                <>
                  <p style={S.sectionLabel}>Your imports</p>
                  <select
                    style={S.select}
                    value={selectedPassageId}
                    onChange={(e) => setSelectedPassageId(e.target.value)}
                  >
                    <option value="">— Select a passage —</option>
                    {passages.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.title} — {new Date(p.uploaded_at).toLocaleDateString()}
                      </option>
                    ))}
                  </select>

                  {selectedPassageContent && (
                    <>
                      <p style={S.sectionLabel}>Preview</p>
                      <div style={S.previewBox}>
                        {selectedPassageContent.slice(0, 300)}…
                      </div>
                    </>
                  )}

                  <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
                    <button
                      style={{
                        ...S.btnPrimary,
                        opacity: !selectedPassageId ? 0.45 : 1,
                        cursor: !selectedPassageId ? "not-allowed" : "pointer",
                      }}
                      onClick={() => setStep(3)}
                      disabled={!selectedPassageId}
                    >
                      Confirm Selection →
                    </button>

                    <button style={S.btnGhost} onClick={() => navigate("/home")}>
                      + Upload New File
                    </button>
                  </div>
                </>
              )}
            </>
          )}

          {/* ═══ SCREEN 3 — Write + Results ═══ */}
          {step === 3 && (
            <>
              <button
                style={S.backBtn}
                onClick={() => {
                  setStep(mode === "existing_text" ? 2 : 1);
                  setResults(null);
                  setResolved({});
                  setDismissed({});
                }}
              >
                ← Back
              </button>

              <p style={S.eyebrow}>Step 3 of 3</p>
              <h1 style={S.h1}>Start writing your <em style={{ fontStyle: "italic" }}>ideas</em> below.</h1>
              <p style={S.desc}>
                Write freely — SALITAyo will review and gently highlight areas you might want to refine.
              </p>

              {mode === "existing_text" && selectedPassageTitle && (
                <div style={S.refBanner}>
                  📄 <strong style={{ color: "var(--ink)" }}>Reference:</strong> {selectedPassageTitle}
                </div>
              )}

              {mode === "open_topic" && (
                <div style={S.openBanner}>
                  ✏️ <strong>Open Topic</strong> — SALITAyo will identify your topic and evaluate your writing accordingly.
                </div>
              )}

              {/* Language selector */}
              <div style={S.langRow}>
                <span style={{ ...S.sectionLabel, margin: 0, lineHeight: "2.2" }}>Suggestions in</span>
                {[
                  { value: "english", label: "🇺🇸 English" },
                  { value: "filipino", label: "🇵🇭 Filipino" },
                ].map((opt) => (
                  <button
                    key={opt.value}
                    style={language === opt.value ? S.langBtnActive : S.langBtnBase}
                    onClick={() => setLanguage(opt.value)}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>

              {/* Textarea */}
              <textarea
                style={S.textarea}
                placeholder="Start writing here..."
                value={userText}
                rows={8}
                onChange={(e) => setUserText(e.target.value)}
                onFocus={(e) => { e.target.style.borderColor = "var(--clay)"; e.target.style.boxShadow = "0 0 0 3px rgba(184,92,56,0.08)"; }}
                onBlur={(e) => { e.target.style.borderColor = "var(--stone)"; e.target.style.boxShadow = "none"; }}
              />

              {/* Speech */}
              <div style={S.speechRow}>
                {!recording ? (
                  <button style={S.btnRecord} onClick={startRecording} disabled={transcribing}>
                    🎤 {transcribing ? "Transcribing…" : "Start Recording"}
                  </button>
                ) : (
                  <button style={S.btnStop} onClick={stopRecording}>⏹ Stop Recording</button>
                )}

                {recording && (
                  <span style={S.recDot}>
                    <span style={{
                      width: 7, height: 7, borderRadius: "50%",
                      background: "var(--error)", display: "inline-block",
                      animation: "wa-pulse 1s infinite",
                    }} />
                    Recording… speak now
                  </span>
                )}

                {transcribing && (
                  <span style={S.transcribeInfo}>⏳ Sending to Whisper…</span>
                )}

                {transcribeError && (
                  <span style={S.transcribeErr}>{transcribeError}</span>
                )}
              </div>

              <style>{`@keyframes wa-pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }`}</style>

              {/* Analyze */}
              <button
                style={{
                  ...S.btnAnalyze,
                  opacity: loading || !userText.trim() ? 0.45 : 1,
                  cursor: loading || !userText.trim() ? "not-allowed" : "pointer",
                }}
                onClick={handleAnalyze}
                disabled={loading || !userText.trim()}
              >
                {loading ? "Analyzing your writing…" : "Analyze My Writing"}
              </button>

              {error && <p style={S.error}>{error}</p>}

              {/* ── Results ── */}
              {results && (
                <div>
                  <div style={S.resultsHeader}>
                    <span style={S.resultsTitle}>Writing Review</span>
                    <div style={S.countChips}>
                      <div style={S.chipIssues}>
                        <span style={S.chipNum}>{activeCount}</span> issues
                      </div>
                      <div style={S.chipResolved}>
                        <span style={S.chipNum}>{resolvedCount}</span> resolved
                      </div>
                    </div>
                  </div>

                  {topic && (
                    <div style={S.topicChip}>
                      <strong style={{ color: "var(--ink)" }}>Topic:</strong> {topic}
                    </div>
                  )}

                  {results.length === 0 && (
                    <div style={S.noIssues}>✓ Great job! No issues found in your writing.</div>
                  )}

                  {results.map((item, i) => {
                    if (resolved[i]) return (
                      <div key={i} style={S.resolvedCard}>
                        <span>
                          ✓ <strong>{resolved[i].original}</strong>
                          {" → "}
                          <strong style={{ color: "var(--fern)" }}>{resolved[i].replacement}</strong>
                          <span style={{ fontSize: "0.72rem", color: "var(--hint)", marginLeft: 6 }}>(resolved)</span>
                        </span>
                        <button
                          onClick={() => handleUndo(i)}
                          style={{
                            fontSize: "0.75rem", color: "var(--hint)", background: "none", border: "none",
                            cursor: "pointer", fontFamily: "'DM Sans', sans-serif",
                            textDecoration: "underline", textUnderlineOffset: 3, padding: 0,
                          }}
                        >
                          Undo
                        </button>
                      </div>
                    );

                    if (dismissed[i]) return null;

                    const sColor = severityColor(item.severity);

                    return (
                      <div
                        key={i}
                        style={{ ...S.issueCard, borderColor: sColor === "var(--fern)" ? "var(--stone)" : sColor }}
                      >
                        <div style={S.cardBadges}>
                          <span style={S.badgeType}>{typeLabel(item.type)}</span>
                          <span style={{
                            ...S.badgeType,
                            color: sColor,
                            borderColor: sColor + "44",
                            background: sColor + "10",
                          }}>
                            {severityLabel(item.severity)}
                          </span>
                        </div>

                        <p style={{ fontSize: "0.72rem", textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--hint)", marginBottom: "0.2rem" }}>Original</p>
                        <p style={{ fontFamily: "'Fraunces', serif", fontStyle: "italic", color: "var(--clay)", fontSize: "1.05rem", marginBottom: "0.5rem" }}>
                          {item.original}
                        </p>

                        <p style={{ fontSize: "0.72rem", textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--hint)", marginBottom: "0.2rem", fontWeight: 500 }}>Why flagged</p>
                        <p style={{ fontSize: "0.85rem", color: "var(--muted)", lineHeight: 1.65, fontWeight: 300, marginBottom: "0.75rem" }}>
                          {item.reason}
                        </p>

                        <p style={{ fontSize: "0.72rem", textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--hint)", marginBottom: "0.5rem", fontWeight: 500 }}>Suggestions</p>
                        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginBottom: "0.875rem" }}>
                          {item.suggestions.map((s, j) => (
                            <button
                              key={j}
                              onClick={() => handleSuggestionClick(i, s)}
                              onMouseEnter={(e) => { e.currentTarget.style.borderColor = "var(--fern)"; e.currentTarget.style.background = "rgba(92,110,66,0.07)"; e.currentTarget.style.color = "var(--fern)"; }}
                              onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--stone)"; e.currentTarget.style.background = "var(--sand)"; e.currentTarget.style.color = "var(--ink)"; }}
                              style={{
                                padding: "7px 14px", borderRadius: 10, border: "1.5px solid var(--stone)",
                                background: "var(--sand)", fontFamily: "'DM Sans', sans-serif",
                                fontSize: "0.82rem", color: "var(--ink)", cursor: "pointer", transition: "all 0.2s",
                              }}
                            >
                              {s.replacement}
                              <span style={{ fontSize: "0.72rem", color: "var(--hint)", marginLeft: 4 }}>
                                ({s.similarity_score}% match)
                              </span>
                            </button>
                          ))}
                        </div>

                        <button
                          onClick={() => handleDismiss(i)}
                          style={{
                            fontSize: "0.75rem", color: "var(--hint)", background: "none", border: "none",
                            cursor: "pointer", fontFamily: "'DM Sans', sans-serif",
                            textDecoration: "underline", textUnderlineOffset: 3, padding: 0, transition: "color 0.2s",
                          }}
                        >
                          Ignore this suggestion
                        </button>
                      </div>
                    );
                  })}

                  <div style={S.bottomRow}>
                    <button
                      style={S.btnPrimary}
                      onClick={() =>
                        navigator.clipboard.writeText(userText)
                          .then(() => alert("✅ Text copied to clipboard!"))
                          .catch(() => alert("Failed to copy. Please copy manually."))
                      }
                    >
                      📋 Copy Final Text
                    </button>

                    <button style={S.btnGhost} onClick={resetAll}>
                      ✏️ New Writing Session
                    </button>
                  </div>
                </div>
              )}
            </>
          )}

        </div>
      </div>
    </div>
  );
}