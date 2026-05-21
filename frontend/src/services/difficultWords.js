const STORAGE_KEY = 'salitayo_difficult_words'
const UPDATED_EVENT = 'salitayo:difficult-words-updated'

export function normalizeDifficultWord(word) {
  return String(word || '')
    .replace(/[Â··]/g, '')
    .replace(/[^\p{L}\p{N}'-]/gu, '')
    .trim()
}

export function getDifficultWords() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
    return Array.isArray(saved) ? saved : []
  } catch {
    return []
  }
}

export function saveDifficultWord(word, source = 'reading-restructurer') {
  const cleaned = normalizeDifficultWord(word)
  if (!cleaned || cleaned.length < 2) return getDifficultWords()

  const now = new Date().toISOString()
  const saved = getDifficultWords()
  const existing = saved.find(
    (item) => String(item.word || '').toLowerCase() === cleaned.toLowerCase()
  )

  if (existing) {
    existing.clickCount = Number(existing.clickCount || 0) + 1
    existing.lastSeen = now
    existing.source = existing.source || source
  } else {
    saved.push({
      word: cleaned,
      clickCount: 1,
      firstSeen: now,
      lastSeen: now,
      source,
    })
  }

  saved.sort((a, b) => {
    const countDelta = Number(b.clickCount || 0) - Number(a.clickCount || 0)
    if (countDelta) return countDelta
    return String(b.lastSeen || '').localeCompare(String(a.lastSeen || ''))
  })

  localStorage.setItem(STORAGE_KEY, JSON.stringify(saved))
  window.dispatchEvent(new CustomEvent(UPDATED_EVENT, { detail: saved }))
  return saved
}

export function removeDifficultWord(word) {
  const cleaned = normalizeDifficultWord(word)
  const next = getDifficultWords().filter(
    (item) => String(item.word || '').toLowerCase() !== cleaned.toLowerCase()
  )
  localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
  window.dispatchEvent(new CustomEvent(UPDATED_EVENT, { detail: next }))
  return next
}

export function subscribeDifficultWords(callback) {
  const handler = () => callback(getDifficultWords())
  const customHandler = (event) => callback(event.detail || getDifficultWords())
  window.addEventListener('storage', handler)
  window.addEventListener(UPDATED_EVENT, customHandler)
  return () => {
    window.removeEventListener('storage', handler)
    window.removeEventListener(UPDATED_EVENT, customHandler)
  }
}
