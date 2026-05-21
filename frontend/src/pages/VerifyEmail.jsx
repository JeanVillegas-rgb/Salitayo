import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { resendVerification, verifyEmail } from '../services/authApi'

export default function VerifyEmail() {
  const { token } = useParams()
  const [status, setStatus] = useState('loading')
  const [message, setMessage] = useState('')
  const [email, setEmail] = useState('')
  const [resent, setResent] = useState(false)
  const [resending, setResending] = useState(false)
  const [resendError, setResendError] = useState('')

  useEffect(() => {
    if (!token || token === 'resend') {
      setStatus('error')
      setMessage('Enter your email below to resend the verification link.')
      return
    }

    verifyEmail(token)
      .then((response) => {
        setStatus('success')
        setMessage(response.data.message)
      })
      .catch((error) => {
        setStatus('error')
        setMessage(error.response?.data?.error || 'Verification failed or link has expired.')
      })
  }, [token])

  const handleResend = async () => {
    if (!email) {
      setResendError('Please enter your email address.')
      return
    }
    if (!/\S+@\S+\.\S+/.test(email)) {
      setResendError('Enter a valid email.')
      return
    }

    setResendError('')
    setResending(true)
    try {
      await resendVerification(email)
      setResent(true)
    } catch (error) {
      setResendError(error.response?.data?.error || 'Failed to resend. Check your email address.')
    } finally {
      setResending(false)
    }
  }

  if (status === 'loading') {
    return (
      <div className="salita-root auth-centered">
        <div className="auth-card auth-card-centered">
          <div className="status-icon loading" />
          <div className="card-title">Verifying<i>...</i></div>
          <div className="card-sub">Just a moment while we confirm your email.</div>
        </div>
      </div>
    )
  }

  if (status === 'success') {
    return (
      <div className="salita-root auth-centered">
        <div className="auth-card auth-card-centered">
          <div className="status-icon success">
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#5C6E42" strokeWidth="2" strokeLinecap="round">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          </div>
          <div className="eyebrow">All done</div>
          <div className="card-title">Email verified<i>!</i></div>
          <div className="card-sub">{message}</div>
          <Link to="/login" className="btn-primary">Go to login</Link>
        </div>
      </div>
    )
  }

  return (
    <div className="salita-root auth-centered">
      <div className="auth-card auth-card-centered">
        <div className="status-icon error" />
        {!resent ? (
          <>
            <div className="eyebrow">Verification</div>
            <div className="card-title">Check your link<i>.</i></div>
            <div className="card-sub">{message}</div>

            <div className="field auth-left-field">
              <label className="flabel">Your email</label>
              <input
                className={`finput ${resendError ? 'finput-error' : ''}`}
                type="email"
                placeholder="you@email.com"
                value={email}
                onChange={(event) => {
                  setEmail(event.target.value)
                  setResendError('')
                }}
                onKeyDown={(event) => event.key === 'Enter' && handleResend()}
              />
              {resendError ? <span className="error-msg">{resendError}</span> : null}
            </div>

            <button className="btn-primary" onClick={handleResend} disabled={resending}>
              {resending ? 'Resending...' : 'Resend verification email'}
            </button>
          </>
        ) : (
          <>
            <div className="eyebrow">Email sent</div>
            <div className="card-title">Check your inbox<i>.</i></div>
            <div className="card-sub">
              A new verification link is on its way to <strong>{email}</strong>.
            </div>
          </>
        )}

        <Link to="/signup" className="auth-link auth-bottom-link">Back to sign up</Link>
      </div>
    </div>
  )
}
