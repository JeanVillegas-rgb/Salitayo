import { useState, useEffect } from 'react'
import axios from 'axios'
import './WritingAssistant.css'
import ImportsPage from './ImportsPage'

const ERROR_TYPE_COLOR = {
  phonetic_sub: '#7c3aed',
  reversal: '#dc2626',
  omission: '#d97706',
  insertion: '#0891b2',
  transposition: '#16a34a',
  language_mix: '#9333ea',
}

const NLI_CONFIG = {
  entailment:    { label: 'Fits context', color: '#16a34a', bg: '#f0fdf4' },
  contradiction: { label: 'Conflicts',    color: '#dc2626', bg: '#fef2f2' },
  neutral:       { label: 'Neutral',      color: '#6b7280', bg: '#f8fafc' },
  off_topic:     { label: 'Off-topic',    color: '#9333ea', bg: '#faf5ff' },
}

function computeCorrectedText(originalText, errors) {
  let result = originalText
  let offset = 0
  const sorted = [...errors].sort((a, b) => a.start - b.start)
  for (const err of sorted) {
    const adjStart = err.start + offset
    const adjEnd = err.end + offset
    result = result.slice(0, adjStart) + err.correction + result.slice(adjEnd)
    offset += err.correction.length - (err.end - err.start)
  }
  return result
}

function HighlightedText({ text, errors }) {
  if (!errors.length) return <span>{text}</span>

  const parts = []
  let cursor = 0
  const sorted = [...errors].sort((a, b) => a.start - b.start)

  for (const err of sorted) {
    if (err.start > cursor) {
      parts.push(<span key={`plain-${cursor}`}>{text.slice(cursor, err.start)}</span>)
    }
    parts.push(
      <mark
        key={`err-${err.start}`}
        className="highlight"
        style={{ '--err-color': ERROR_TYPE_COLOR[err.error_type] || '#f59e0b' }}
        title={`${err.error_type_label}: ${err.word} -> ${err.correction}`}
      >
        {text.slice(err.start, err.end)}
      </mark>
    )
    cursor = err.end
  }
  if (cursor < text.length) {
    parts.push(<span key="plain-end">{text.slice(cursor)}</span>)
  }
  return <>{parts}</>
}

function ComparisonModal({ modal, originalText, onClose, onApply }) {
  const { error, candidate } = modal
  const color = ERROR_TYPE_COLOR[error.error_type] || '#f59e0b'

  const before = originalText.slice(0, error.start)
  const after = originalText.slice(error.end)

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true">
        <div className="modal-header">
          <h2>Review Change</h2>
          <button className="modal-close" onClick={onClose} aria-label="Close">x</button>
        </div>

        <div className="comparison-grid">
          <div className="comparison-panel original-panel">
            <h3>Original</h3>
            <p className="comparison-text">
              {before}
              <mark className="wrong-mark" style={{ '--wrong-color': color }}>{error.word}</mark>
              {after}
            </p>
          </div>

          <div className="comparison-divider">-&gt;</div>

          <div className="comparison-panel fixed-panel">
            <h3>With change</h3>
            <p className="comparison-text">
              {before}
              <mark className="fix-mark">{candidate}</mark>
              {after}
            </p>
          </div>
        </div>

        <div className="modal-actions">
          <button className="btn-cancel" onClick={onClose}>Back</button>
          <button className="btn-apply" onClick={() => onApply(error, candidate)}>
            Apply Change
          </button>
        </div>
      </div>
    </div>
  )
}

function LanguageSelector({ value, onChange }) {
  const options = [
    { value: 'auto',     label: 'Auto' },
    { value: 'filipino', label: 'Filipino' },
    { value: 'english',  label: 'English' },
  ]
  return (
    <div className="lang-selector">
      <span className="lang-selector-label">Output language</span>
      <div className="lang-pills">
        {options.map(opt => (
          <button
            key={opt.value}
            className={`lang-pill ${value === opt.value ? 'active' : ''}`}
            onClick={() => onChange(opt.value)}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  )
}

function LanguageBadge({ language }) {
  const configs = {
    filipino:            { text: 'Filipino',         color: '#2563eb' },
    taglish_to_filipino: { text: 'Filipino output',  color: '#7c3aed' },
    taglish_to_english:  { text: 'English output',   color: '#0891b2' },
  }
  const cfg = configs[language]
  if (!cfg) return null
  return <div className="lang-badge" style={{ '--badge-color': cfg.color }}>{cfg.text}</div>
}

function PassageSelector({ passages, selectedId, onSelect, fetchingContent }) {
  return (
    <div className="passage-selector">
      <div className="passage-selector-label-row">
        <label className="passage-selector-label" htmlFor="passage-select">
          Reference passage
        </label>
        {fetchingContent && (
          <span className="passage-loading">Loading...</span>
        )}
      </div>
      <select
        id="passage-select"
        className="passage-select"
        value={selectedId ?? ''}
        onChange={e => onSelect(e.target.value ? parseInt(e.target.value) : null)}
      >
        <option value="">No reference - skip context check</option>
        {passages.map(p => (
          <option key={p.id} value={p.id}>{p.title}</option>
        ))}
      </select>
    </div>
  )
}

function ErrorCard({ err, onCandidateClick, onUndoClick }) {
  const color = ERROR_TYPE_COLOR[err.error_type] || '#f59e0b'

  return (
    <div className="error-card" style={{ '--card-color': color }}>
      <div className="error-card-header">
        <span className="error-word">"{err.word}"</span>
        <span className="arrow">-&gt;</span>
        <span className="correction">"{err.correction}"</span>
        <span className="error-type-badge" style={{ background: color }}>
          {err.error_type_label}
        </span>
        {err.applied && (
          <button className="undo-btn" onClick={() => onUndoClick(err)}>
            Undo
          </button>
        )}
      </div>
      <p className="error-feedback">{err.feedback}</p>
      <div className="candidates">
        <span className="candidates-label">Suggestions: </span>
        {err.candidates.map((c, i) => (
          <button
            key={i}
            className={`candidate-pill ${c === err.correction ? 'best' : ''}`}
            onClick={() => onCandidateClick(err, c)}
            title="Click to preview this correction"
          >
            {c}
          </button>
        ))}
      </div>
      <div className="confidence-row">
        <span>Classifier: {(err.error_type_confidence * 100).toFixed(0)}%</span>
      </div>
    </div>
  )
}

function ContextAlignmentSection({ results }) {
  if (!results || results.length === 0) return null

  return (
    <div className="context-alignment-section">
      <h2 className="context-alignment-heading">Context Alignment</h2>
      {results.map((item, i) => {
        const cfg = NLI_CONFIG[item.nli_label] || NLI_CONFIG.neutral
        return (
          <div
            key={i}
            className="alignment-card"
            style={{ '--align-color': cfg.color, '--align-bg': cfg.bg }}
          >
            <div className="alignment-card-header">
              <span
                className="alignment-badge"
                style={{ background: cfg.color }}
              >
                {cfg.label}
              </span>
              <span className="alignment-confidence">
                {(item.nli_confidence * 100).toFixed(0)}% confidence
              </span>
              <span className="alignment-sim">
                similarity {(item.similarity_score * 100).toFixed(0)}%
              </span>
            </div>
            <div className="alignment-sentences">
              <div className="alignment-sentence-row">
                <span className="alignment-sentence-label">Your sentence</span>
                <p className="alignment-sentence-text learner-sent">
                  {item.learner_sentence}
                </p>
              </div>
              <div className="alignment-sentence-row">
                <span className="alignment-sentence-label">Reference match</span>
                <p className="alignment-sentence-text reference-sent">
                  {item.reference_sentence}
                </p>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default function WritingAssistant() {
  const [page, setPage] = useState('coach')
  const [text, setText] = useState('')
  const [result, setResult] = useState(null)
  const [targetLanguage, setTargetLanguage] = useState('auto')
  const [loading, setLoading] = useState(false)
  const [apiError, setApiError] = useState(null)
  const [compareModal, setCompareModal] = useState(null)
  const [copied, setCopied] = useState(false)

  const [passages, setPassages] = useState([])
  const [selectedPassage, setSelectedPassage] = useState(null)
  const [fetchingContent, setFetchingContent] = useState(false)

  const [alignmentResults, setAlignmentResults] = useState(null)
  const [alignmentLoading, setAlignmentLoading] = useState(false)
  const [alignmentError, setAlignmentError] = useState(null)

  useEffect(() => {
    axios.get('/api/passages/')
      .then(res => setPassages(res.data.passages))
      .catch(() => {})
  }, [])

  if (page === 'imports') {
    return <ImportsPage onBack={() => setPage('coach')} />
  }

  async function handlePassageSelect(id) {
    if (!id) {
      setSelectedPassage(null)
      return
    }
    setFetchingContent(true)
    try {
      const { data } = await axios.get(`/api/passages/${id}/`)
      setSelectedPassage(data)
    } catch {
      setSelectedPassage(null)
    } finally {
      setFetchingContent(false)
    }
  }

  async function handleAnalyze() {
    if (!text.trim()) return
    setLoading(true)
    setApiError(null)
    setResult(null)
    setAlignmentResults(null)
    setAlignmentError(null)
    try {
      const { data } = await axios.post('/api/analyze/', { text, target_language: targetLanguage })
      setResult({
        ...data,
        errors: data.errors.map(e => ({
          ...e,
          applied: false,
          originalCorrection: e.correction,
        })),
      })
    } catch (e) {
      setApiError(e.response?.data?.text?.[0] || e.message || 'Request failed.')
    } finally {
      setLoading(false)
    }
  }

  async function handleCheckAlignment() {
    if (!text.trim() || !selectedPassage?.content) return
    setAlignmentLoading(true)
    setAlignmentError(null)
    setAlignmentResults(null)
    try {
      const { data } = await axios.post('/api/alignment/', {
        text,
        reference_passage: selectedPassage.content,
      })
      setAlignmentResults(data.context_alignment_results)
    } catch (e) {
      setAlignmentError(e.response?.data?.detail || e.message || 'Alignment check failed.')
    } finally {
      setAlignmentLoading(false)
    }
  }

  function handleCandidateClick(error, candidate) {
    setCompareModal({ error, candidate })
  }

  function handleApplyChange(error, candidate) {
    const updatedErrors = result.errors.map(err =>
      err.start === error.start
        ? { ...err, correction: candidate, applied: true }
        : err
    )
    const appliedErrors = updatedErrors.filter(e => e.applied)
    const newText = appliedErrors.length > 0
      ? computeCorrectedText(result.original_text, appliedErrors)
      : result.original_text
    setResult({ ...result, errors: updatedErrors })
    setText(newText)
    setCompareModal(null)
  }

  function handleUndoChange(error) {
    const updatedErrors = result.errors.map(err =>
      err.start === error.start
        ? { ...err, correction: err.originalCorrection, applied: false }
        : err
    )
    const appliedErrors = updatedErrors.filter(e => e.applied)
    const newText = appliedErrors.length > 0
      ? computeCorrectedText(result.original_text, appliedErrors)
      : result.original_text
    setResult({ ...result, errors: updatedErrors })
    setText(newText)
  }

  function handleCopy() {
    if (!text) return
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1800)
    })
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-main">
          <div>
            <h1>SALITAyo</h1>
            <p className="subtitle">Assistive Writing Coach for Dyslexic Learners</p>
          </div>
          <button className="header-imports-btn" onClick={() => setPage('imports')}>
            Reference Passages
          </button>
        </div>
      </header>

      <main className="app-main">
        <section className="input-section">
          <div className="label-row">
            <label className="input-label" htmlFor="writing-input">
              Type or paste your writing below
            </label>
            {text && (
              <button className="copy-btn" onClick={handleCopy} title="Copy text">
                {copied ? 'Copied!' : 'Copy'}
              </button>
            )}
          </div>
          <PassageSelector
            passages={passages}
            selectedId={selectedPassage?.id ?? null}
            onSelect={handlePassageSelect}
            fetchingContent={fetchingContent}
          />

          <LanguageSelector value={targetLanguage} onChange={setTargetLanguage} />

          <textarea
            id="writing-input"
            className="writing-area"
            value={text}
            onChange={e => setText(e.target.value)}
            placeholder="e.g. The quik brwon fox jmped ovr the lzy dog."
            rows={6}
          />
          <button
            className="analyze-btn"
            onClick={handleAnalyze}
            disabled={loading || !text.trim()}
          >
            {loading ? 'Analyzing...' : 'Analyze Writing'}
          </button>
        </section>

        {apiError && <div className="error-banner">{apiError}</div>}

        {result && (
          <section className="results-section">
            <LanguageBadge language={result.language} />
            <div className="stats-bar">
              <div className="stat">
                <span className="stat-value">{result.word_count}</span>
                <span className="stat-label">Words</span>
              </div>
              <div className="stat">
                <span className="stat-value">{result.error_count}</span>
                <span className="stat-label">Errors found</span>
              </div>
              <div className="stat">
                <span className="stat-value">{result.errors.filter(e => e.applied).length}</span>
                <span className="stat-label">Errors solved</span>
              </div>
            </div>

            {result.error_count > 0 && (
              <>
                <div className="text-panel">
                  <h2>Your text</h2>
                  <p className="annotated-text">
                    <HighlightedText text={result.original_text} errors={result.errors} />
                  </p>
                </div>

                <div className="text-panel">
                  <h2>Suggested correction</h2>
                  <p className="corrected-text">{result.corrected_text}</p>
                </div>

                <div className="errors-list">
                  <h2>Error details ({result.error_count})</h2>
                  {result.errors.map((err, i) => (
                    <ErrorCard
                      key={`${err.start}-${i}`}
                      err={err}
                      onCandidateClick={handleCandidateClick}
                      onUndoClick={handleUndoChange}
                    />
                  ))}
                </div>
              </>
            )}

            {result.error_count === 0 && (
              <div className="no-errors">
                No spelling errors detected. Great writing!
              </div>
            )}

            {selectedPassage && (
              <div className="alignment-trigger">
                <button
                  className="check-alignment-btn"
                  onClick={handleCheckAlignment}
                  disabled={alignmentLoading}
                >
                  {alignmentLoading ? 'Checking alignment...' : 'Check Alignment'}
                </button>
                {alignmentError && (
                  <div className="error-banner" style={{ marginTop: '0.5rem' }}>
                    {alignmentError}
                  </div>
                )}
              </div>
            )}

            {alignmentResults && (
              <ContextAlignmentSection results={alignmentResults} />
            )}
          </section>
        )}
      </main>

      {compareModal && (
        <ComparisonModal
          modal={compareModal}
          originalText={result.original_text}
          onClose={() => setCompareModal(null)}
          onApply={handleApplyChange}
        />
      )}
    </div>
  )
}
