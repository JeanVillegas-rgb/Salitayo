import { useState } from 'react'
import ReadingRestructurer from './ReadingRestructurer'
import WritingAssistant from './WritingAssistant'
import './styles.css'

export default function App() {
  const [activeTab, setActiveTab] = useState('reading')

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
          <span className="user-avatar">JV</span>
        </div>
      </header>

      {/* Main Content Area with Animated Switch */}
      <div className="portal-content-wrapper">
        {activeTab === 'reading' ? (
          <div className="tab-content-fade-in">
            <ReadingRestructurer />
          </div>
        ) : (
          <div className="tab-content-fade-in">
            <WritingAssistant />
          </div>
        )}
      </div>
    </div>
  )
}
