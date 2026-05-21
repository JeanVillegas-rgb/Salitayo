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

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  },
)

export async function login(payload) {
  const { data } = await api.post('/api/auth/login/', payload)
  localStorage.setItem('token', data.token)
  localStorage.setItem('user', JSON.stringify(data.user))
  return data
}

export function register(payload) {
  return api.post('/api/auth/register/', payload)
}

export function verifyEmail(token) {
  return api.get(`/api/auth/verify-email/${token}/`)
}

export function resendVerification(email) {
  return api.post('/api/auth/resend-verification/', { email })
}

export async function logout() {
  await api.post('/api/auth/logout/')
  localStorage.removeItem('token')
  localStorage.removeItem('user')
}
