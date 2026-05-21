import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { login } from '../services/authApi'

const initialForm = { email: '', password: '' }

export default function Login() {
  const navigate = useNavigate()
  const [form, setForm] = useState(initialForm)
  const [errors, setErrors] = useState({})
  const [loading, setLoading] = useState(false)

  const set = (field, value) => {
    setForm((current) => ({ ...current, [field]: value }))
    setErrors((current) => ({ ...current, [field]: '' }))
  }

  const validate = () => {
    const nextErrors = {}
    if (!form.email) {
      nextErrors.email = 'Email is required.'
    } else if (!/\S+@\S+\.\S+/.test(form.email)) {
      nextErrors.email = 'Enter a valid email.'
    }
    if (!form.password) nextErrors.password = 'Password is required.'
    setErrors(nextErrors)
    return Object.keys(nextErrors).length === 0
  }

  const handleSubmit = async () => {
    if (!validate()) return
    setLoading(true)
    try {
      await login(form)
      navigate('/home')
    } catch (error) {
      const message =
        error.response?.data?.non_field_errors?.[0] ||
        error.response?.data?.detail ||
        'Invalid email or password.'
      setErrors({ password: message })
    } finally {
      setLoading(false)
    }
  }

  if (localStorage.getItem('token')) {
    return <Navigate to="/home" replace />
  }

  return (
    <div className="salita-root">
      <div className="left-panel">
        <div className="aside-content">
          <div className="aside-logo">SALIT<em>A</em>yo</div>
          <div className="aside-heading">Welcome<br />back<i>.</i></div>
          <div className="aside-sub">
            Pick up right where you left off. Your words are waiting.
          </div>
          <div className="aside-pills">
            <div className="aside-pill"><span className="pill-dot" />Speech accuracy tracking</div>
            <div className="aside-pill"><span className="pill-dot" />Personalised flashcards</div>
            <div className="aside-pill"><span className="pill-dot" />Progress over time</div>
          </div>
        </div>
      </div>

      <div className="right-panel">
        <div className="auth-card">
          <div className="eyebrow">Log in</div>
          <div className="card-title">Good to see you<i>.</i></div>
          <div className="card-sub">Enter your credentials to continue.</div>

          <div className="auth-form">
            <Field label="Email" error={errors.email}>
              <input
                className={`finput ${errors.email ? 'finput-error' : ''}`}
                type="email"
                placeholder="you@email.com"
                value={form.email}
                onChange={(event) => set('email', event.target.value)}
                onKeyDown={(event) => event.key === 'Enter' && handleSubmit()}
              />
            </Field>

            <Field label="Password" error={errors.password}>
              <input
                className={`finput ${errors.password ? 'finput-error' : ''}`}
                type="password"
                placeholder="Password"
                value={form.password}
                onChange={(event) => set('password', event.target.value)}
                onKeyDown={(event) => event.key === 'Enter' && handleSubmit()}
              />
            </Field>

            <button className="btn-primary" onClick={handleSubmit} disabled={loading}>
              {loading ? 'Logging in...' : 'Log in'}
            </button>
          </div>

          <div className="or-line">or</div>

          <p className="footer-text">
            No account yet? <Link to="/signup" className="auth-link">Sign up free</Link>
          </p>
          <p className="footer-text">
            Didn't get the email?{' '}
            <Link to="/verify-email/resend" className="auth-link">Resend verification</Link>
          </p>
        </div>
      </div>
    </div>
  )
}

function Field({ label, error, children }) {
  return (
    <div className="field">
      <label className="flabel">{label}</label>
      {children}
      {error ? <span className="error-msg">{error}</span> : null}
    </div>
  )
}
