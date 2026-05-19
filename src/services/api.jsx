import axios from 'axios'

const api = axios.create({ baseURL: 'http://localhost:8000' })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Token ${token}`
  if (!(config.data instanceof FormData)) {
    config.headers['Content-Type'] ??= 'application/json'
  }
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export const register = (payload) => api.post('/auth/register/', payload)
export const verifyEmail = (token) => api.get(`/auth/verify-email/${token}/`)
export const login = async (payload) => {
  const { data } = await api.post('/auth/login/', payload)
  localStorage.setItem('token', data.token)
  localStorage.setItem('user', JSON.stringify(data.user))
  return data
}
export const logout = async () => {
  await api.post('/auth/logout/')
  localStorage.removeItem('token')
  localStorage.removeItem('user')
}
export const resendVerification = (email) => api.post('/auth/resend-verification/', { email })

export const getPassages = () => api.get('/system/passages/')
export const getPassageById = (id) => api.get(`/system/passages/${id}/`)
export const deletePassage = (id) => api.delete(`/system/passages/${id}/delete/`)
export const uploadPassage = (formData) => api.post('/system/passages/upload/', formData, {
  headers: { 'Content-Type': 'multipart/form-data' },
})

export const analyzeWriting = (payload) => api.post('/system/writing/analyze/', payload)
export const updateFlagged = (payload) => api.post('/system/writing/flag/update/', payload)
export const transcribeAudio = (formData) => api.post('/system/transcribe/', formData, {
  headers: { 'Content-Type': 'multipart/form-data' },
})

const WP = '/system'

function wpResult(promise) {
  return promise
    .then(({ data }) => ({ data, error: null }))
    .catch((err) => ({
      data: null,
      error: err.response?.data?.error ?? err.response?.data?.detail ?? err.message ?? 'Network error',
    }))
}

export const wpImportWords = (words) => wpResult(api.post(`${WP}/words/import/`, { words }))
export const wpStartSession = (sessionSize = 10, posTag = null, wordIds = null) =>
  wpResult(api.post(`${WP}/session/start/`, {
    session_size: sessionSize,
    ...(posTag ? { pos_tag: posTag } : {}),
    ...(wordIds?.length ? { word_ids: wordIds } : {}),
  }))
export const wpSubmitAttempt = (audioBlob, language = 'en') => {
  const form = new FormData()
  form.append('audio', audioBlob, 'attempt.webm')
  form.append('language', language === 'fil' ? 'fil' : 'en')
  return wpResult(api.post(`${WP}/session/attempt/`, form))
}
export const wpEndSession = () => wpResult(api.post(`${WP}/session/end/`, {}))
export const wpGetSessionStatus = () => wpResult(api.get(`${WP}/session/status/`))
export const wpSyncPosTags = () => wpResult(api.post(`${WP}/words/sync-pos/`, {}))
export const wpGetWords = (filters = {}) => {
  const params = new URLSearchParams(
    Object.fromEntries(Object.entries(filters).filter(([, v]) => v != null && v !== ''))
  ).toString()
  return wpResult(api.get(`${WP}/words/${params ? `?${params}` : ''}`))
}
export const wpGetWordDetail = (word) =>
  wpResult(api.get(`${WP}/words/${encodeURIComponent(word.toLowerCase())}/`))
export const wpTrainModel = (scope = 'user') => wpResult(api.post(`${WP}/train/`, { scope }))
export const wpGetSessionHistory = () => wpResult(api.get(`${WP}/session/history/`))
