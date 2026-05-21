import axios from 'axios'

const api = axios.create({ baseURL: '' })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Token ${token}`
  if (!(config.data instanceof FormData)) {
    config.headers['Content-Type'] ??= 'application/json'
  }
  return config
})

const WP = '/api/system'

function wpResult(promise) {
  return promise
    .then(({ data }) => ({ data, error: null }))
    .catch((err) => ({
      data: null,
      error: err.response?.data?.error || err.response?.data?.detail || err.message || 'Request failed',
    }))
}

export const wpImportWords = (words) => wpResult(api.post(`${WP}/words/import/`, { words }))
export const wpStartSession = (sessionSize = 10, posTag = null, wordIds = null) =>
  wpResult(api.post(`${WP}/session/start/`, {
    session_size: sessionSize,
    ...(posTag ? { pos_tag: posTag } : {}),
    ...(wordIds ? { word_ids: wordIds } : {}),
  }))
export const wpSubmitAttempt = (audioBlob, language = 'en') => {
  const form = new FormData()
  form.append('audio', audioBlob, 'attempt.webm')
  form.append('language', language)
  return wpResult(api.post(`${WP}/session/attempt/`, form))
}
export const wpEndSession = () => wpResult(api.post(`${WP}/session/end/`, {}))
export const wpGetSessionStatus = () => wpResult(api.get(`${WP}/session/status/`))
export const wpSyncPosTags = () => wpResult(api.post(`${WP}/words/sync-pos/`, {}))
export const wpGetWords = (filters = {}) => {
  const params = new URLSearchParams(
    Object.fromEntries(Object.entries(filters).filter(([, v]) => v != null && v !== ''))
  )
  return wpResult(api.get(`${WP}/words/${params ? `?${params}` : ''}`))
}
export const wpGetWordDetail = (word) =>
  wpResult(api.get(`${WP}/words/${encodeURIComponent(word.toLowerCase())}/`))
export const wpTrainModel = (scope = 'user') => wpResult(api.post(`${WP}/train/`, { scope }))
export const wpGetSessionHistory = () => wpResult(api.get(`${WP}/session/history/`))
