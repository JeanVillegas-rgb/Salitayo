import { useState } from 'react'
import { Link } from 'react-router-dom'
import { register } from '../services/authApi'

const initialForm = {
  email: '',
  display_name: '',
  first_name: '',
  last_name: '',
  middle_name: '',
  role: 'STUDENT',
  password: '',
  confirm_password: '',
}

export default function SignUp() {
  const [step, setStep] = useState(1)
  const [form, setForm] = useState(initialForm)
  const [errors, setErrors] = useState({})
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)

  const set = (field, value) => {
    setForm((current) => ({ ...current, [field]: value }))
    setErrors((current) => ({ ...current, [field]: '' }))
  }

  const validateStep1 = () => {
    const nextErrors = {}
    if (!form.email) {
      nextErrors.email = 'Email is required.'
    } else if (!/\S+@\S+\.\S+/.test(form.email)) {
      nextErrors.email = 'Enter a valid email.'
    }
    if (!form.display_name) nextErrors.display_name = 'Display name is required.'
    if (!form.first_name) nextErrors.first_name = 'First name is required.'
    if (!form.last_name) nextErrors.last_name = 'Last name is required.'
    setErrors(nextErrors)
    return Object.keys(nextErrors).length === 0
  }

  const validateStep2 = () => {
    const nextErrors = {}
    if (!form.password) {
      nextErrors.password = 'Password is required.'
    } else if (form.password.length < 8) {
      nextErrors.password = 'Minimum 8 characters.'
    }
    if (!form.confirm_password) {
      nextErrors.confirm_password = 'Please confirm your password.'
    } else if (form.password !== form.confirm_password) {
      nextErrors.confirm_password = 'Passwords do not match.'
    }
    setErrors(nextErrors)
    return Object.keys(nextErrors).length === 0
  }

  const handleNext = () => {
    if (validateStep1()) setStep(2)
  }

  const handleSubmit = async () => {
    if (!validateStep2()) return
    setLoading(true)
    try {
      await register(form)
      setDone(true)
    } catch (error) {
      const data = error.response?.data
      if (data && typeof data === 'object') {
        const serverErrors = {}
        Object.keys(data).forEach((key) => {
          serverErrors[key] = Array.isArray(data[key]) ? data[key][0] : data[key]
        })
        setErrors(serverErrors)
      } else {
        setErrors({ email: 'Connection failed. Is Django running?' })
      }
      setStep(1)
    } finally {
      setLoading(false)
    }
  }

  if (done) {
    return (
      <div className="salita-root auth-centered">
        <div className="auth-card auth-card-centered">
          <div className="status-icon success">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#5C6E42" strokeWidth="2" strokeLinecap="round">
              <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
              <polyline points="22,6 12,13 2,6" />
            </svg>
          </div>
          <div className="eyebrow">Almost there</div>
          <div className="card-title">Check your inbox<i>.</i></div>
          <div className="card-sub">
            We sent a verification link to <strong>{form.email}</strong>.
          </div>
          <Link to="/login" className="btn-primary">Go to login</Link>
        </div>
      </div>
    )
  }

  return (
    <div className="salita-root">
      <div className="left-panel">
        <div className="aside-content">
          <div className="aside-logo">SALIT<em>A</em>yo</div>
          <div className="aside-heading">Start your<br />reading<br /><i>journey.</i></div>
          <div className="aside-sub">
            Join students and teachers building better reading habits together.
          </div>
          <div className="aside-pills">
            <div className="aside-pill"><span className="pill-dot" />Free to get started</div>
            <div className="aside-pill"><span className="pill-dot" />No reading level required</div>
            <div className="aside-pill"><span className="pill-dot" />Learn at your own pace</div>
          </div>
        </div>
      </div>

      <div className="right-panel">
        <div className="auth-card auth-signup-card">
          <div className="steps">
            <div className={`step-dot ${step >= 1 ? 'active' : ''}`} />
            <div className="step-line" />
            <div className={`step-dot ${step >= 2 ? 'active' : ''}`} />
          </div>

          <div className="eyebrow">{step === 1 ? 'Step 1 of 2' : 'Step 2 of 2'}</div>
          <div className="card-title">
            {step === 1 ? <>Create your account<i>.</i></> : <>Secure your account<i>.</i></>}
          </div>
          <div className="card-sub">
            {step === 1 ? 'Tell us a little about yourself.' : 'Set a strong password to protect your account.'}
          </div>

          {step === 1 ? (
            <div className="auth-form">
              <div className="field">
                <label className="flabel">I am a</label>
                <div className="role-group">
                  <button
                    type="button"
                    className={`role-btn ${form.role === 'STUDENT' ? 'role-active' : ''}`}
                    onClick={() => set('role', 'STUDENT')}
                  >
                    Student
                  </button>
                  <button
                    type="button"
                    className={`role-btn ${form.role === 'PROFESSOR' ? 'role-active' : ''}`}
                    onClick={() => set('role', 'PROFESSOR')}
                  >
                    Teacher
                  </button>
                </div>
              </div>

              <div className="row3">
                <Field label="First name" error={errors.first_name}>
                  <input className={`finput ${errors.first_name ? 'finput-error' : ''}`} value={form.first_name} onChange={(event) => set('first_name', event.target.value)} />
                </Field>
                <Field label="Middle">
                  <input className="finput" value={form.middle_name} onChange={(event) => set('middle_name', event.target.value)} />
                </Field>
                <Field label="Last name" error={errors.last_name}>
                  <input className={`finput ${errors.last_name ? 'finput-error' : ''}`} value={form.last_name} onChange={(event) => set('last_name', event.target.value)} />
                </Field>
              </div>

              <Field label="Display name" error={errors.display_name}>
                <input className={`finput ${errors.display_name ? 'finput-error' : ''}`} value={form.display_name} onChange={(event) => set('display_name', event.target.value)} />
              </Field>

              <Field label="Email" error={errors.email}>
                <input className={`finput ${errors.email ? 'finput-error' : ''}`} type="email" value={form.email} onChange={(event) => set('email', event.target.value)} />
              </Field>

              <button className="btn-primary" onClick={handleNext}>Continue</button>
            </div>
          ) : (
            <div className="auth-form">
              <Field label="Password" error={errors.password}>
                <input className={`finput ${errors.password ? 'finput-error' : ''}`} type="password" value={form.password} onChange={(event) => set('password', event.target.value)} />
              </Field>

              <Field label="Confirm password" error={errors.confirm_password}>
                <input className={`finput ${errors.confirm_password ? 'finput-error' : ''}`} type="password" value={form.confirm_password} onChange={(event) => set('confirm_password', event.target.value)} />
              </Field>

              <div className="btn-row">
                <button className="btn-ghost" onClick={() => setStep(1)}>Back</button>
                <button className="btn-primary" onClick={handleSubmit} disabled={loading}>
                  {loading ? 'Creating account...' : 'Create account'}
                </button>
              </div>
            </div>
          )}

          <p className="footer-text">
            Already have an account? <Link to="/login" className="auth-link">Log in</Link>
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
