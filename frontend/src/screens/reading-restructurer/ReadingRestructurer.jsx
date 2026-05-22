import { useEffect, useState } from 'react'
import { saveDifficultWord } from '../../services/difficultWords'
import './diagnostics.css'

const BASELINE_SECONDS_PER_CHUNK = 8

function createInitialSessionMetrics() {
  return {
    replayRate: 0,
    timeOnChunk: 0,
    dropPoint: 0,
    vocabFriction: 0,
    replays: {},
    lastStartTime: null,
    totalDuration: 0,
    chunkCount: 0,
    clickedWords: [],
    furthestChunk: 0,
  }
}

export default function ReadingRestructurer() {
  const [inputText, setInputText] = useState('')
  const [output, setOutput] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [modelMode, setModelMode] = useState('')
  const [activeChunkId, setActiveChunkId] = useState(null)
  const [ttsStatus, setTtsStatus] = useState({}) // { chunkId: 'neural' | 'browser' | 'loading' }
  const [augmentedWords, setAugmentedWords] = useState([])
  const [targetLanguage, setTargetLanguage] = useState('en')
  const [mixedOutput, setMixedOutput] = useState('taglish')
  const [adaptiveSupports, setAdaptiveSupports] = useState({
    autoChunking: false,
    autoChunkMinLength: 7,
    playbackSpeed: 1,
    aggressiveness: 'BALANCED',
  })
  const [adaptiveNotices, setAdaptiveNotices] = useState([])
  
  // OBSERVATIONAL METRICS (Adaptive Diagnostics)
  const [sessionMetrics, setSessionMetrics] = useState(createInitialSessionMetrics)

  const handleChunkClick = (chunkId) => {
    const now = Date.now()
    setActiveChunkId(chunkId)
    setSessionMetrics(prev => {
      const chunkCount = output?.chunks?.length || prev.chunkCount || 1
      const replays = {
        ...prev.replays,
        [chunkId]: (prev.replays[chunkId] || 0) + 1,
      }
      const totalReplays = Object.values(replays).reduce((sum, count) => sum + count, 0)
      const chunkNum = parseInt(String(chunkId).split('-')[1], 10) || 1
      const furthestChunk = Math.max(prev.furthestChunk, chunkNum)
      const elapsedSeconds = prev.lastStartTime ? (now - prev.lastStartTime) / 1000 : 0
      const totalDuration = prev.totalDuration + Math.max(0, elapsedSeconds)
      const visitedCount = Object.keys(replays).length || 1
      const avgSecondsPerVisitedChunk = totalDuration / visitedCount

      return {
        ...prev,
        replays,
        replayRate: Number((totalReplays / chunkCount).toFixed(2)),
        timeOnChunk: Number((avgSecondsPerVisitedChunk / BASELINE_SECONDS_PER_CHUNK).toFixed(2)),
        dropPoint: Math.round((furthestChunk / chunkCount) * 100),
        lastStartTime: now,
        totalDuration,
        chunkCount,
        furthestChunk,
      }
    })
  }

  const handleChunkDoubleClick = (chunkId) => {
    if (activeChunkId === chunkId) {
      setActiveChunkId(null) // Double click to stop
    }
  }

  useEffect(() => {
    if (!output?.chunks?.length || !activeChunkId) return undefined

    const timer = window.setInterval(() => {
      const now = Date.now()
      setSessionMetrics(prev => {
        if (!prev.lastStartTime) return prev
        const chunkCount = output.chunks.length || prev.chunkCount || 1
        const visitedCount = Object.keys(prev.replays).length || 1
        const activeElapsed = (now - prev.lastStartTime) / 1000
        const liveTotalDuration = prev.totalDuration + Math.max(0, activeElapsed)
        const avgSecondsPerVisitedChunk = liveTotalDuration / visitedCount

        return {
          ...prev,
          timeOnChunk: Number((avgSecondsPerVisitedChunk / BASELINE_SECONDS_PER_CHUNK).toFixed(2)),
          chunkCount,
        }
      })
    }, 1000)

    return () => window.clearInterval(timer)
  }, [activeChunkId, output?.chunks])

  useEffect(() => {
    if (!output?.chunks?.length) return

    const recommendations = []
    const replayRate = Number(sessionMetrics.replayRate || 0)
    const timeOnChunk = Number(sessionMetrics.timeOnChunk || 0)
    const vocabFriction = Number(sessionMetrics.vocabFriction || 0)
    const hasActiveStruggleSignal = replayRate > 0.6 || timeOnChunk > 1.5 || vocabFriction > 3
    const severeStruggle = replayRate > 1.25 || timeOnChunk > 2.25 || vocabFriction > 5
    const extremeStruggle = replayRate > 2 || timeOnChunk > 3 || vocabFriction > 8
    const targetPlaybackSpeed = extremeStruggle ? 0.65 : severeStruggle ? 0.75 : timeOnChunk > 1.5 ? 0.85 : adaptiveSupports.playbackSpeed
    const targetChunkMinLength = extremeStruggle ? 5 : severeStruggle ? 6 : 7

    if (replayRate > 0.6 && !adaptiveSupports.autoChunking) {
      recommendations.push({
        key: 'autoChunking',
        label: `Word chunking turned on for words with ${targetChunkMinLength}+ letters.`,
      })
    } else if (adaptiveSupports.autoChunking && targetChunkMinLength < adaptiveSupports.autoChunkMinLength) {
      recommendations.push({
        key: 'chunkMinLength',
        label: `Word chunking expanded to words with ${targetChunkMinLength}+ letters.`,
      })
    }
    if (targetPlaybackSpeed < adaptiveSupports.playbackSpeed) {
      recommendations.push({
        key: 'playbackSpeed',
        label: `Playback speed adjusted to ${targetPlaybackSpeed.toFixed(2)}x.`,
      })
    }
    if (
      Number(sessionMetrics.furthestChunk || 0) > 0 &&
      Number(sessionMetrics.dropPoint || 0) < 50 &&
      hasActiveStruggleSignal &&
      adaptiveSupports.aggressiveness !== 'AGGRESSIVE'
    ) {
      recommendations.push({
        key: 'aggressiveness',
        label: 'Simplification aggressiveness adjusted to aggressive mode.',
      })
    }
    if (vocabFriction > 3 && !adaptiveSupports.autoChunking) {
      recommendations.push({
        key: 'autoChunking',
        label: `Difficult vocabulary chunking turned on for words with ${targetChunkMinLength}+ letters.`,
      })
    }

    const unique = recommendations.filter(
      (item, index, list) => list.findIndex((candidate) => candidate.key === item.key) === index
    )
    if (!unique.length) return

    const keys = unique.map((item) => item.key)
    setAdaptiveSupports(prev => ({
      autoChunking: prev.autoChunking || keys.includes('autoChunking'),
      autoChunkMinLength: (keys.includes('autoChunking') || keys.includes('chunkMinLength'))
        ? Math.min(prev.autoChunkMinLength, targetChunkMinLength)
        : prev.autoChunkMinLength,
      playbackSpeed: keys.includes('playbackSpeed') ? targetPlaybackSpeed : prev.playbackSpeed,
      aggressiveness: keys.includes('aggressiveness') ? 'AGGRESSIVE' : prev.aggressiveness,
    }))
    setAdaptiveNotices(unique.map((item) => item.label))

    if (keys.includes('aggressiveness')) {
      runRestructure(null, {
        ...buildAdaptiveMetrics({
          sdp_ratio: 0.25,
          replay_rate: Math.max(Number(sessionMetrics.replayRate || 0), 0.7),
          toc_ratio: Math.max(Number(sessionMetrics.timeOnChunk || 1), 1.6),
          vfi_count: Math.max(Number(sessionMetrics.vocabFriction || 0), 4),
        }),
      })
    }
  }, [adaptiveSupports, output?.chunks, sessionMetrics])


  function speakChunk(chunkId, text, lang, ttsUrl) {
    // 1. UNIVERSAL STOP: Check if anything is speaking
    const isNeuralPlaying = window._activeAudio && !window._activeAudio.paused
    const isBrowserSpeaking = window.speechSynthesis.speaking
    
    if (isNeuralPlaying || isBrowserSpeaking) {
      if (window._activeAudio) {
        window._activeAudio.pause()
        window._activeAudio.currentTime = 0
      }
      window.speechSynthesis.cancel()
      
      // If clicking the SAME chunk, just stop and return
      if (window._currentPlayingId === chunkId) {
        window._currentPlayingId = null
        setTtsStatus(prev => ({ ...prev, [chunkId]: '' }))
        return
      }
    }
    
    // Clear other statuses
    setTtsStatus({})

    // 2. LEVER RESPONSE: Use backend-provided playback speed
    const metadataSpeed = Number.parseFloat(output?.metadata?.levers?.playback_speed) || 1.0
    const speed = adaptiveSupports.playbackSpeed || metadataSpeed

    const cleanText = text.replace(/[·-]/g, '')

    // PRIORITIZE NEURAL WORD-FLOW TTS (via Backend Proxy)
    setTtsStatus(prev => ({ ...prev, [chunkId]: 'loading' }))
    window._currentPlayingId = chunkId
    
    // Dynamically find the backend port (fallback to 8000 if not detected)
    const backendBase = window.location.port === '8000' ? '' : 'http://localhost:8000'
    const neuralTtsUrl = `${backendBase}/api/tts-speech/?text=${encodeURIComponent(cleanText)}&lang=${lang}`
    
    // Create audio and keep reference to avoid GC
    const audio = new Audio()
    audio.crossOrigin = "anonymous" // Prevent CORS blocks
    audio.src = neuralTtsUrl
    audio.playbackRate = speed
    window._activeAudio = audio 
    
    audio.oncanplaythrough = () => {
      if (window._currentPlayingId === chunkId) {
        setTtsStatus(prev => ({ ...prev, [chunkId]: 'neural' }))
        audio.play().catch(e => {
          console.error("Neural playback play() failed:", e)
          fallbackToBrowserVoice(cleanText, lang, speed, chunkId)
        })
      }
    }

    audio.onended = () => {
      setTtsStatus(prev => ({ ...prev, [chunkId]: '' }))
      window._currentPlayingId = null
    }

    audio.onerror = (e) => {
      console.error("Neural TTS loading failed:", e)
      setTtsStatus(prev => ({ ...prev, [chunkId]: 'browser' }))
      fallbackToBrowserVoice(cleanText, lang, speed, chunkId)
    }

    // Force load to trigger the fetch immediately
    audio.load()

    // --- METRICS TRACKING ---
    const now = Date.now()
    setSessionMetrics(prev => {
      const replayCount = (prev.replays[chunkId] || 0) + 1
      const totalReplays = Object.values({ ...prev.replays, [chunkId]: replayCount }).reduce((a, b) => a + b, 0)
      const chunkCount = output?.chunks?.length || 1
      const rr = totalReplays / chunkCount

      // SDP (Session Drop Point): Highest chunk accessed vs total
      const chunkNum = parseInt(chunkId.split('-')[1]) || 1
      const furthest = Math.max(prev.furthestChunk, chunkNum)
      const sdp = furthest / chunkCount

      // ToC (Time on Chunk): Basic duration tracking
      let durationContribution = 0
      if (prev.lastStartTime) {
        durationContribution = (now - prev.lastStartTime) / 1000
      }

      return {
        ...prev,
        replays: { ...prev.replays, [chunkId]: replayCount },
        replayRate: rr.toFixed(2),
        dropPoint: (sdp * 100).toFixed(0),
        lastStartTime: now,
        totalDuration: prev.totalDuration + durationContribution,
        furthestChunk: furthest
      }
    })
  }

  function fallbackToBrowserVoice(text, lang, speed, chunkId) {
    window.speechSynthesis.cancel() 
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.onend = () => {
      setTtsStatus(prev => ({ ...prev, [chunkId]: '' }))
      window._currentPlayingId = null
    }
    const voices = window.speechSynthesis.getVoices()
    let selectedVoice = null

    if (lang === 'tl') {
      selectedVoice = voices.find(v => v.lang.includes('PH') || v.name.toLowerCase().includes('filipino'))
      utterance.lang = 'fil-PH'
    } else {
      selectedVoice = voices.find(v => v.lang.includes('US') || v.lang.includes('GB'))
      utterance.lang = 'en-US'
    }

    if (selectedVoice) utterance.voice = selectedVoice
    utterance.rate = speed 
    window.speechSynthesis.speak(utterance)
  }

  function buildAdaptiveMetrics(overrides = {}) {
    return {
      replay_rate: Number(sessionMetrics.replayRate || 0),
      toc_ratio: Number(sessionMetrics.timeOnChunk || 1),
      sdp_ratio: Number(sessionMetrics.dropPoint || 100) / 100,
      vfi_count: Number(sessionMetrics.vocabFriction || 0),
      ...overrides,
    }
  }

  async function runRestructure(event, metricOverrides = null) {
    event?.preventDefault()
    const trimmedText = inputText.trim()

    if (!trimmedText) {
      setOutput(null)
      setError('Enter text to restructure.')
      setLoading(false)
      return
    }

    setLoading(true)
    setError('')

    try {
      const requestOptions = {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          input_text: trimmedText,
          source_context: `reading simplification AGGR:${adaptiveSupports.aggressiveness}`,
          target_language: targetLanguage,
          metrics: metricOverrides || buildAdaptiveMetrics(),
          mixed_output: targetLanguage === 'mix' ? mixedOutput : undefined
        }),
      }

      let response = await fetch('/api/restructure/', requestOptions)
      if ([500, 502, 503, 504].includes(response.status)) {
        await new Promise((resolve) => window.setTimeout(resolve, 800))
        response = await fetch('/api/restructure/', requestOptions)
      }

      const responseText = await response.text()
      let data = {}
      if (responseText) {
        try {
          data = JSON.parse(responseText)
        } catch {
          throw new Error(responseText.slice(0, 180) || `Request failed with status ${response.status}`)
        }
      }

      if (!response.ok || data.success === false) {
        const message = data.error || data.detail || `Request failed with status ${response.status}`
        throw new Error(message)
      }

      setOutput(data)
      setAugmentedWords(data.augmented_words || [])
      setModelMode(data.mode || '')
      setActiveChunkId(null)
      setSessionMetrics({
        ...createInitialSessionMetrics(),
        chunkCount: data.chunks?.length || 0,
      })
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading(false)
    }
  }

  function handleTargetLanguageChange(language) {
    setTargetLanguage(language)
    if (output) {
      setOutput(null)
      setModelMode('')
      setAugmentedWords([])
    }
  }

  function handleMixedOutputChange(mode) {
    setMixedOutput(mode)
    if (output) {
      setOutput(null)
      setModelMode('')
      setAugmentedWords([])
    }
  }

  const renderMixedToggles = () => {
    if (targetLanguage !== 'mix') return null
    return (
      <div className="input-language-control" style={{ marginTop: '0.15rem', borderTop: '1px dashed rgba(30, 30, 30, 0.08)', paddingTop: '0.65rem' }} aria-label="Choose mixed output target">
        <span className="input-language-label">Output Target</span>
        <div className="output-language-toggle">
          <button
            type="button"
            className={`toggle-btn ${mixedOutput === 'taglish' ? 'active' : ''}`}
            onClick={() => handleMixedOutputChange('taglish')}
          >
            Taglish
          </button>
          <button
            type="button"
            className={`toggle-btn ${mixedOutput === 'tagalog' ? 'active' : ''}`}
            onClick={() => handleMixedOutputChange('tagalog')}
          >
            Pure Tagalog
          </button>
          <button
            type="button"
            className={`toggle-btn ${mixedOutput === 'english' ? 'active' : ''}`}
            onClick={() => handleMixedOutputChange('english')}
          >
            Pure English
          </button>
        </div>
      </div>
    )
  }

  function clearCurrentText() {
    setInputText('')
    setOutput(null)
    setError('')
    setModelMode('')
    setActiveChunkId(null)
    setTtsStatus({})
    setAugmentedWords([])
    setSessionMetrics(createInitialSessionMetrics())
    setAdaptiveSupports({ autoChunking: false, autoChunkMinLength: 7, playbackSpeed: 1, aggressiveness: 'BALANCED' })
    setAdaptiveNotices([])
    window.speechSynthesis.cancel()
    if (window._activeAudio) {
      window._activeAudio.pause()
      window._activeAudio.currentTime = 0
    }
    window._currentPlayingId = null
  }

  function syllableChunk(word) {
    if (!word || word.length < 4) return word
    const lower = word.toLowerCase()
    const pieces = []
    let index = 0
    while (index < lower.length) {
      // Basic vowel-based chunking
      const match = lower.substring(index).match(/[^aeiouy]*[aeiouy]+(?:[^aeiouy](?![aeiouy]))?/)
      if (!match) {
        pieces.push(word.substring(index))
        break
      }
      pieces.push(word.substring(index, index + match[0].length))
      index += match[0].length
    }
    return pieces.join('-')
  }

  function shouldAutoChunkWord(word) {
    const cleaned = String(word || '').replace(/[-Â·]/g, '')
    return adaptiveSupports.autoChunking && cleaned.length >= adaptiveSupports.autoChunkMinLength && syllableChunk(cleaned).includes('-')
  }

  function toggleAugmentWord(word) {
    saveDifficultWord(word)
    const cleanWord = word.replace(/[-·]/g, '').toLowerCase()
    setSessionMetrics(prev => {
      const clickedWords = prev.clickedWords.includes(cleanWord)
        ? prev.clickedWords
        : [...prev.clickedWords, cleanWord]
      return {
        ...prev,
        clickedWords,
        vocabFriction: clickedWords.length,
      }
    })
    setAugmentedWords((prev) => {
      const isAugmented = prev.some(w => w.replace(/[-·]/g, '').toLowerCase() === cleanWord)
      if (isAugmented) return prev.filter(w => w.replace(/[-·]/g, '').toLowerCase() !== cleanWord)
      return [...prev, word]
    })
  }

  function renderChunkText(chunk) {
    const text = chunk?.text || ''
    const highlightTerms = new Set((chunk?.highlight_terms || []).map(t => t.toLowerCase()))

    const pattern = /([A-Za-z·\-]+|[^A-Za-z·\-]+)/g
    const parts = text.match(pattern) || []

    return parts.map((part, index) => {
      if (!/[A-Za-z]/.test(part)) {
        return <span key={`${chunk.chunk_id}-sep-${index}`}>{part}</span>
      }

      const cleanPart = part.replace(/[-·]/g, '').toLowerCase()
      const isAugmented = augmentedWords.some(w => w.replace(/[-·]/g, '').toLowerCase() === cleanPart)
      const isHighlighted = highlightTerms.has(cleanPart)

      const shouldChunk = isAugmented || shouldAutoChunkWord(part)
      const displayWord = shouldChunk ? syllableChunk(part.replace(/[-·]/g, '')) : part

      return (
        <span
          key={`${chunk.chunk_id}-part-${index}`}
          className={`clickable-word ${shouldChunk ? 'user-augmented' : ''} ${isHighlighted ? 'term-highlight' : ''}`}
          onClick={() => toggleAugmentWord(part)}
          title="Click to hyphenate"
          style={{ cursor: 'pointer' }}
        >
          {displayWord}
        </span>
      )
    })
  }

  function renderClickableText(text) {
    const pattern = /([A-Za-z·\-áéíóúñÁÉÍÓÚÑ]+|[^A-Za-z·\-áéíóúñÁÉÍÓÚÑ]+)/g
    const parts = text.match(pattern) || []

    return parts.map((part, index) => {
      if (!/[A-Za-záéíóúñ]/.test(part)) {
        return <span key={`text-sep-${index}`}>{part}</span>
      }

      const cleanPart = part.replace(/[-·]/g, '').toLowerCase()
      const isAugmented = augmentedWords.some(w => w.replace(/[-·]/g, '').toLowerCase() === cleanPart)
      
      const shouldChunk = isAugmented || shouldAutoChunkWord(part)
      const displayWord = shouldChunk ? syllableChunk(part.replace(/[-·]/g, '')) : part
      const className = `clickable-word ${shouldChunk ? 'user-augmented' : ''}`

      return (
        <span
          key={`text-part-${index}`}
          className={className}
          onClick={() => toggleAugmentWord(part)}
          title="Click to hyphenate"
          style={{ cursor: 'pointer' }}
        >
          {displayWord}
        </span>
      )
    })
  }

  function splitDisplayLines(text) {
    return String(text || '')
      .split(/(?<=[.!?])\s+(?=[A-Z])/) 
      .map((line) => line.trim())
      .filter(Boolean)
  }

  const hasLiveStruggleSignal = Number(sessionMetrics.replayRate || 0) > 0.6 || Number(sessionMetrics.timeOnChunk || 0) > 1.5 || Number(sessionMetrics.vocabFriction || 0) > 3
  const liveDiagnosticMetrics = {
    rr: {
      label: 'Replay Rate (RR)',
      value: Number(sessionMetrics.replayRate || 0).toFixed(2),
      status: Number(sessionMetrics.replayRate || 0) > 0.6 ? 'STRUGGLE' : 'FLUENCY',
    },
    toc: {
      label: 'Time Ratio (ToC)',
      value: Number(sessionMetrics.timeOnChunk || 0).toFixed(2),
      status: Number(sessionMetrics.timeOnChunk || 0) > 1.5 ? 'STRUGGLE' : 'FLUENCY',
    },
    vfi: {
      label: 'Vocab Friction (VFI)',
      value: String(sessionMetrics.vocabFriction || 0),
      status: Number(sessionMetrics.vocabFriction || 0) > 3 ? 'STRUGGLE' : 'FLUENCY',
    },
    sdp: {
      label: 'Deep Point (SDP)',
      value: `${Math.round(sessionMetrics.dropPoint || 0)}%`,
      status: Number(sessionMetrics.dropPoint || 0) < 50 && hasLiveStruggleSignal ? 'STRUGGLE' : 'FLUENCY',
    },
  }

  const evaluation = output?.evaluation?.restructurer
  const evaluationRows = evaluation ? [
    {
      metric: 'FRE',
      reason: 'Readability',
      before: evaluation.fre_original,
      after: evaluation.fre_restructured,
      change: evaluation.fre_delta,
      note: 'Higher is easier',
    },
    {
      metric: 'FKGL',
      reason: 'Grade-level reduction',
      before: evaluation.fkgl_original,
      after: evaluation.fkgl_simplified,
      change: evaluation.fkgl_delta,
      note: 'Positive change means lower grade level',
    },
    {
      metric: 'GFI',
      reason: 'Linguistic complexity',
      before: evaluation.gfi_original,
      after: evaluation.gfi_restructured,
      change: evaluation.gfi_delta,
      note: 'Positive change means lower complexity',
    },
    {
      metric: 'ASL',
      reason: 'Sentence simplification',
      before: evaluation.asl_original,
      after: evaluation.asl_restructured,
      change: evaluation.asl_delta,
      note: 'Average words per sentence',
    },
    {
      metric: 'ASW',
      reason: 'Vocabulary simplification',
      before: evaluation.asw_original,
      after: evaluation.asw_restructured,
      change: evaluation.asw_delta,
      note: 'Average syllables per word',
    },
    {
      metric: 'BERTScore',
      reason: 'Semantic preservation',
      before: null,
      after: evaluation.bertscore_f1,
      change: null,
      note: evaluation.bertscore_method === 'bert-score' ? 'Transformer similarity F1' : 'Lexical fallback F1',
    },
    {
      metric: 'ERR',
      reason: 'Entity preservation',
      before: evaluation.entity_count,
      after: evaluation.err,
      change: null,
      note: `${evaluation.preserved_entity_count ?? 0}/${evaluation.entity_count ?? 0} entities preserved`,
    },
  ] : []

  function formatMetricValue(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return '-'
    return Number(value).toFixed(2)
  }

  const aiStateLabel = loading ? 'Processing' : output ? 'Ready' : 'Standing by'

  return (
    <main className="app-shell">
      <section className="panel">
        <div className="reading-hero">
          <div>
            <p className="eyebrow">SALITAyo</p>
            <h1>Reading Restructurer</h1>
            <p className="reading-subtitle">Academic text restructuring with adaptive reading support.</p>
          </div>
          <div className="reading-ai-badge">
            <span>{aiStateLabel}</span>
            <strong>{modelMode || 'loading model'}</strong>
          </div>
        </div>

        <form className="form-card" onSubmit={runRestructure}>
          <div className="input-language-control" aria-label="Choose restructuring language">
            <span className="input-language-label">Language</span>
            <div className="output-language-toggle">
              <button
                type="button"
                className={`toggle-btn ${targetLanguage === 'en' ? 'active' : ''}`}
                onClick={() => handleTargetLanguageChange('en')}
              >
                English
              </button>
              <button
                type="button"
                className={`toggle-btn ${targetLanguage === 'tl' ? 'active' : ''}`}
                onClick={() => handleTargetLanguageChange('tl')}
              >
                Tagalog
              </button>
              <button
                type="button"
                className={`toggle-btn ${targetLanguage === 'mix' ? 'active' : ''}`}
                onClick={() => handleTargetLanguageChange('mix')}
              >
                Mixed
              </button>
            </div>
          </div>
          {renderMixedToggles()}
          <label htmlFor="inputText">Academic text</label>
          <textarea
            id="inputText"
            value={inputText}
            onChange={(event) => setInputText(event.target.value)}
            placeholder="Paste or type the text you want to restructure."
            rows={8}
            spellCheck="false"
          />
          <div className="form-actions">
            <button
              type="button"
              className="secondary-btn"
              onClick={clearCurrentText}
              disabled={loading || (!inputText && !output && !error)}
            >
              Delete
            </button>
            <button type="submit" disabled={loading || !inputText.trim()}>
              {loading ? 'Restructuring...' : 'Restructure'}
            </button>
          </div>
          <p className="live-status">{loading ? 'Working on your text...' : 'Click Restructure when your text is ready.'}</p>
        </form>

        {output?.diagnostic_log && (
          <div className="diagnostic-card" style={{ marginTop: '1rem' }}>
            <header className="diagnostic-header">
              <div className="title-group">
                <svg className="icon-search" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                </svg>
                <h3>Adaptive Diagnostic Log</h3>
              </div>
              <span className="live-badge">LIVE COMPUTATION</span>
            </header>

            <div className="metrics-grid">
              {Object.entries(liveDiagnosticMetrics).map(([key, metric]) => (
                <div key={key} className="metric-item">
                  <p className="metric-label">{metric.label}</p>
                  <div className="metric-value-row">
                    <span className="metric-value">{metric.value}</span>
                    <span className={`status-tag ${metric.status.toLowerCase()}`}>{metric.status}</span>
                  </div>
                </div>
              ))}
            </div>

            {adaptiveNotices.length ? (
              <div className="adaptive-confirmation">
                <div>
                  <strong>Adaptive support applied</strong>
                  <p>{adaptiveNotices.join(' ')}</p>
                </div>
              </div>
            ) : null}

            <div className="levers-section">
              <div className="lever-row">
                <span className="lever-label-main">ACTIVE LEVERS</span>
                <span className="lever-label-main">ENGINE RESPONSE MODES:</span>
              </div>
              <div className="lever-row">
                <div className="lever-detail">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"></path></svg>
                  <span>Aggressiveness: <strong>{adaptiveSupports.aggressiveness}</strong></span>
                </div>
                <div className="lever-detail">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"></circle><path d="M12 6v6l4 2"></path></svg>
                  <span>Playback Speed: <strong>{adaptiveSupports.playbackSpeed.toFixed(2)}x</strong></span>
                </div>
              </div>
              <div className="lever-row" style={{ marginTop: '0.5rem' }}>
                <div className="lever-detail">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 7V4a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v3"></path><path d="M9 11v9a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2v-9"></path><path d="M20 7H4"></path></svg>
                  <span>Chunking: <strong>{adaptiveSupports.autoChunking ? `AUTO (${adaptiveSupports.autoChunkMinLength}+ letters)` : output.metadata?.levers?.chunk_size}</strong></span>
                </div>
              </div>
            </div>
          </div>
        )}

        {error ? <p className="error">{error}</p> : null}

        {output && (
          <div className="reading-result-ribbon">
            <div className="reading-result-badges">
              <span className="simple-label muted-label">
                {output.metadata?.mode?.toUpperCase() || 'STABLE-CORE'}
              </span>
              <span className="simple-label">SIMPLIFIED</span>
            </div>
            <span className="reading-result-count">{output.chunks?.length || 0} chunks</span>
          </div>
        )}
      </section>

      <section className="panel output-panel">
        <h2>API response</h2>
        {output ? (
          <>
            <div className="output-block">
              <div className="section-heading">
                <h3>Restructured text</h3>
                <span className="simple-label">
                  {targetLanguage === 'tl'
                    ? 'TAGALOG'
                    : targetLanguage === 'mix'
                      ? `MIXED (${mixedOutput.toUpperCase()})`
                      : 'ENGLISH'}
                </span>
              </div>
              <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginBottom: '0.85rem' }}>
                {(output.mode?.toLowerCase().includes('groq') || output.diagnostic_log?.mode?.toLowerCase().includes('groq')) && (
                  <span className="simple-label gemma-badge" style={{ background: '#000', color: '#fff' }}>GROQ AI ACTIVE</span>
                )}
                {Object.values(ttsStatus).includes('neural') && <span className="simple-label gemma-badge" style={{ background: '#dcfce7', color: '#166534' }}>GROQ AUDIO ACTIVE</span>}
                {output.mode?.includes('deterministic') && <span className="simple-label fallback-badge" style={{ background: '#f1f5f9', color: '#475569' }}>SALITAyo STABLE CORE</span>}
                {(output.mode === 'gemma-unavailable' || output.mode === 'fallback') && <span className="simple-label fallback-badge">FALLBACK MODE</span>}
                <span className="simple-label">SIMPLIFIED</span>
              </div>
              <div className="full-text-preview" style={{ fontFamily: output.metadata?.font_family, fontSize: output.metadata?.text_size }}>
                <p className="full-text-line">
                  {renderClickableText(output.restructured_text)}
                </p>
              </div>
              {augmentedWords.length ? (
                <p className="muted" style={{ marginTop: '1rem' }}>Augmented words: {augmentedWords.join(', ')}</p>
              ) : null}
              {output.metadata?.ner_protected_terms?.length ? (
                <p className="muted" style={{ marginTop: '0.5rem' }}>
                  BERT-protected words: {output.metadata.ner_protected_terms.join(', ')}
                </p>
              ) : (
                <p className="muted" style={{ marginTop: '0.5rem' }}>BERT-protected words: none detected.</p>
              )}
            </div>

            <div className="output-block">
              <div className="section-heading">
                <h3>Chunks</h3>
              </div>
              <div className="chunk-list">
                {output.chunks?.map((chunk, index) => (
                  <article 
                    key={chunk.chunk_id} 
                    className={`chunk-card clickable-chunk ${activeChunkId === chunk.chunk_id ? 'active-focus' : ''}`}
                    onClick={() => handleChunkClick(chunk.chunk_id)}
                    onDoubleClick={() => handleChunkDoubleClick(chunk.chunk_id)}
                    style={{ cursor: 'pointer', transition: 'all 0.3s ease' }}
                  >
                    <div className="chunk-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <span className="chunk-label">Sentence {index + 1}</span>
                        {ttsStatus[chunk.chunk_id] === 'neural' && <span className="simple-label" style={{ fontSize: '0.6rem', background: '#dcfce7', color: '#166534' }}>NEURAL</span>}
                        {ttsStatus[chunk.chunk_id] === 'loading' && <span className="simple-label" style={{ fontSize: '0.6rem', background: '#f1f5f9', color: '#475569' }}>...</span>}
                      </div>
                      <button 
                        className="speaker-btn"
                        onClick={(e) => {
                          e.stopPropagation();
                          const speakLang = targetLanguage === 'mix' 
                            ? (mixedOutput === 'english' ? 'en' : 'tl') 
                            : targetLanguage;
                          speakChunk(chunk.chunk_id, chunk.text, speakLang);
                        }}
                        style={{ background: 'transparent', color: '#5f6f52', padding: '4px', display: 'flex' }}
                      >
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>
                          <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path>
                        </svg>
                      </button>
                    </div>
                    <p className="chunk-text-sample" style={{ fontFamily: output.metadata?.font_family, fontSize: output.metadata?.text_size }}>
                      {renderChunkText(chunk)}
                    </p>
                  </article>
                ))}
              </div>
            </div>
          </>
        ) : (
          <p className="placeholder">The response will appear here.</p>
        )}
      </section>
    </main>
  )
}
