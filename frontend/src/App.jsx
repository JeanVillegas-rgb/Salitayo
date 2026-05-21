import { useState } from 'react'
import { Navigate, Route, Routes, useNavigate } from 'react-router-dom'
import ProtectedRoute from './components/ProtectedRoute'
import Login from './pages/Login'
import SignUp from './pages/SignUp'
import VerifyEmail from './pages/VerifyEmail'
import ReadingRestructurer from './ReadingRestructurer'
import WritingAssistant from './WritingAssistant'
import WordProficiencyTab from './WordProficiencyTab'
import { logout } from './services/authApi'
import './styles.css'

function PortalShell() {
  const [activeTab, setActiveTab] = useState('wordproficiency')
  const navigate = useNavigate()
  const user = JSON.parse(localStorage.getItem('user') || '{}')
  const initials = `${user.first_name?.[0] || ''}${user.last_name?.[0] || ''}` || 'JV'

  const handleLogout = async () => {
    try {
      await logout()
    } catch {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
    } finally {
      navigate('/login')
    }
  }

  return (
    <div className="portal-container">
      {/* Premium Dashboard Header & Tab Switcher */}
      <header className="portal-navbar">
        <div className="portal-logo-group">
          <div className="portal-logo-glow"></div>
          <span className="portal-logo-text">SALITAyo</span>
          <span className="portal-logo-badge">PRO</span>
        </div>

        <nav className="portal-tabs" aria-label="Portal main navigation">
          <button
            className={`portal-tab-btn ${activeTab === 'wordproficiency' ? 'active' : ''}`}
            onClick={() => setActiveTab('wordproficiency')}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" className="tab-icon">
              <path d="M12 2L2 7l10 5 10-5-10-5z"></path>
              <path d="M2 17l10 5 10-5"></path>
              <path d="M2 12l10 5 10-5"></path>
            </svg>
            <span>Word Proficiency</span>
          </button>

          <button
            className={`portal-tab-btn ${activeTab === 'reading' ? 'active' : ''}`}
            onClick={() => setActiveTab('reading')}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" className="tab-icon">
              <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
              <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
            </svg>
            <span>Reading Restructurer</span>
          </button>

          <button
            className={`portal-tab-btn ${activeTab === 'writing' ? 'active' : ''}`}
            onClick={() => setActiveTab('writing')}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" className="tab-icon">
              <path d="M12 20h9"></path>
              <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
            </svg>
            <span>Writing Assistant</span>
          </button>
        </nav>

        <div className="portal-user-profile">
          <span className="user-avatar">{initials.toUpperCase()}</span>
          <button className="portal-logout-btn" type="button" onClick={handleLogout}>
            Logout
          </button>
        </div>
      </header>

      {/* Main Content Area with Animated Switch */}
      <div className="portal-content-wrapper">
        {activeTab === 'wordproficiency' && (
          <div className="tab-content-fade-in">
            <WordProficiencyTab />
          </div>
        )}
        {activeTab === 'reading' && (
          <div className="tab-content-fade-in">
            <ReadingRestructurer />
          </div>
        )}
        {activeTab === 'writing' && (
          <div className="tab-content-fade-in">
            <WritingAssistant />
          </div>
        )}
      </div>
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<SignUp />} />
      <Route path="/verify-email/:token" element={<VerifyEmail />} />
      <Route path="/verify-email/resend" element={<VerifyEmail />} />
      <Route
        path="/home"
        element={
          <ProtectedRoute>
            <PortalShell />
          </ProtectedRoute>
        }
      />
      <Route path="/" element={<Navigate to={localStorage.getItem('token') ? '/home' : '/login'} replace />} />
      <Route path="*" element={<Navigate to="/home" replace />} />
    </Routes>
  )
}
