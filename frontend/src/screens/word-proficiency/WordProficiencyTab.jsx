import { useState, useEffect } from 'react'
import axios from 'axios'
import WordProficiency from './WordProficiency'
import { wpGetSessionStatus } from '../../services/wpApi'
import './WordProficiency.css'

async function ensureWpAuth() {
  if (localStorage.getItem('token')) return true
  try {
    const { data } = await axios.post('/api/auth/login/', {
      email: 'student@salitayo.dev',
      password: 'salitayo-dev',
    })
    localStorage.setItem('token', data.token)
    if (data.user) localStorage.setItem('user', JSON.stringify(data.user))
    return true
  } catch {
    return false
  }
}

export default function WordProficiencyTab() {
  const [resumeState, setResumeState] = useState(null)
  const [checking, setChecking] = useState(true)
  const [authFailed, setAuthFailed] = useState(false)

  useEffect(() => {
    let cancelled = false

    ;(async () => {
      const authed = await ensureWpAuth()
      if (cancelled) return
      if (!authed) {
        setAuthFailed(true)
        setChecking(false)
        return
      }

      const { data } = await wpGetSessionStatus()
      if (!cancelled) {
        if (data?.active) setResumeState(data)
        setChecking(false)
      }
    })()

    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="wp-root wp-tab-shell">
      {checking ? (
        <p className="wp-tab-loading">Loading…</p>
      ) : authFailed ? (
        <p className="wp-tab-auth-hint">
          Word Proficiency needs the backend running. Start Django, then run{' '}
          <code>python manage.py ensure_wp_dev_user</code>.
        </p>
      ) : (
        <WordProficiency
          resumeState={resumeState}
          onResumeConsumed={() => setResumeState(null)}
        />
      )}
    </div>
  )
}
