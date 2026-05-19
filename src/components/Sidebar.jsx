import { NavLink, useNavigate } from "react-router-dom";
import { logout } from "../services/api";

const NAV = [
  {
    to: "/home",
    label: "Home",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
        <path d="M3 9.5L12 3l9 6.5V20a1 1 0 01-1 1H4a1 1 0 01-1-1V9.5z"/>
        <path d="M9 21V12h6v9"/>
      </svg>
    ),
  },
  {
    to: "/reading",
    label: "Reading Restructurer",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
        <path d="M2 6h4l3 12h6l3-12h4"/>
        <path d="M6 12h12"/>
      </svg>
    ),
  },
  {
    to: "/writing",
    label: "Writing Assistant",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
        <path d="M12 20h9"/>
        <path d="M16.5 3.5a2.121 2.121 0 013 3L7 19l-4 1 1-4L16.5 3.5z"/>
      </svg>
    ),
  },
  {
    to: "/wordproficiency",
    label: "Word Proficiency",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
        <path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.4L12 17l-6.2 4.3 2.4-7.4L2 9.4h7.6L12 2z"/>
      </svg>
    ),
  },
  {
    to: "/settings",
    label: "Settings",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
        <circle cx="12" cy="12" r="3"/>
        <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/>
      </svg>
    ),
  },
];

export default function Sidebar() {
  const navigate = useNavigate();
  const user = JSON.parse(localStorage.getItem("user") || "{}");

  const handleLogout = async () => {
    try {
      await logout();
    } catch {
      // clear anyway if request fails
      localStorage.removeItem("token");
      localStorage.removeItem("user");
    }
    navigate("/login");
  };

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,wght@0,300;1,300&family=DM+Sans:wght@300;400;500&display=swap');

        .sidebar {
          width: 240px;
          min-height: 100vh;
          background: var(--moss, #3D4A2E);
          display: flex;
          flex-direction: column;
          position: fixed;
          top: 0; left: 0;
          z-index: 100;
          padding: 0;
          flex-shrink: 0;
        }

        /* top brand */
        .sb-brand {
          padding: 1.75rem 1.5rem 1.25rem;
          border-bottom: 1px solid rgba(255,255,255,0.08);
          margin-bottom: 0.5rem;
        }
        .sb-logo {
          font-family: 'Fraunces', serif;
          font-size: 1.3rem;
          font-weight: 300;
          color: white;
          letter-spacing: 0.02em;
          text-decoration: none;
          display: block;
        }
        .sb-logo em { font-style: italic; color: #D4845A; }
        .sb-user {
          margin-top: 0.5rem;
          font-size: 0.78rem;
          color: rgba(255,255,255,0.45);
          font-family: 'DM Sans', sans-serif;
          font-weight: 300;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        /* nav links */
        .sb-nav {
          flex: 1;
          display: flex;
          flex-direction: column;
          gap: 2px;
          padding: 0.25rem 0.75rem;
        }

        .sb-link {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          padding: 0.7rem 0.875rem;
          border-radius: 10px;
          color: rgba(255,255,255,0.6);
          text-decoration: none;
          font-family: 'DM Sans', sans-serif;
          font-size: 0.875rem;
          font-weight: 400;
          transition: all 0.18s ease;
          cursor: pointer;
          border: none;
          background: none;
          width: 100%;
          text-align: left;
        }
        .sb-link:hover {
          background: rgba(255,255,255,0.07);
          color: rgba(255,255,255,0.9);
        }
        .sb-link.active {
          background: rgba(212,132,90,0.18);
          color: #D4845A;
          font-weight: 500;
        }
        .sb-link.active svg { stroke: #D4845A; }

        .sb-link svg {
          flex-shrink: 0;
          opacity: 0.8;
          transition: opacity 0.18s;
        }
        .sb-link:hover svg { opacity: 1; }

        .sb-section-label {
          font-size: 0.65rem;
          text-transform: uppercase;
          letter-spacing: 0.1em;
          color: rgba(255,255,255,0.25);
          font-family: 'DM Sans', sans-serif;
          padding: 0.875rem 0.875rem 0.25rem;
          font-weight: 500;
        }

        .sb-divider {
          height: 1px;
          background: rgba(255,255,255,0.07);
          margin: 0.5rem 0.75rem;
        }

        /* bottom logout */
        .sb-bottom {
          padding: 0.75rem;
          border-top: 1px solid rgba(255,255,255,0.08);
        }

        .sb-logout {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          padding: 0.7rem 0.875rem;
          border-radius: 10px;
          color: rgba(255,255,255,0.4);
          font-family: 'DM Sans', sans-serif;
          font-size: 0.875rem;
          cursor: pointer;
          border: none;
          background: none;
          width: 100%;
          text-align: left;
          transition: all 0.18s ease;
        }
        .sb-logout:hover {
          background: rgba(184,50,50,0.12);
          color: #e07070;
        }
        .sb-logout:hover svg { stroke: #e07070; }
        .sb-logout svg { flex-shrink: 0; transition: stroke 0.18s; }

        /* layout wrapper — use this in every page */
        .app-layout {
          display: flex;
          min-height: 100vh;
          background: var(--cream, #F7F2EA);
          font-family: 'DM Sans', sans-serif;
        }
        .app-main {
          margin-left: 240px;
          flex: 1;
          min-height: 100vh;
          display: flex;
          flex-direction: column;
        }

        @media (max-width: 768px) {
          .sidebar { display: none; }
          .app-main { margin-left: 0; }
        }
      `}</style>

      <aside className="sidebar">
        {/* Brand */}
        <div className="sb-brand">
          <NavLink to="/home" className="sb-logo">
            SALIT<em>A</em>yo
          </NavLink>
          <div className="sb-user">
            {user.display_name || user.email || "Student"}
          </div>
        </div>

        {/* Main nav */}
        <nav className="sb-nav">
          <div className="sb-section-label">Main</div>

          {NAV.slice(0, 1).map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => `sb-link${isActive ? " active" : ""}`}
            >
              {item.icon}
              {item.label}
            </NavLink>
          ))}

          <div className="sb-section-label" style={{ marginTop: "0.5rem" }}>Modules</div>

          {NAV.slice(1, 4).map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => `sb-link${isActive ? " active" : ""}`}
            >
              {item.icon}
              {item.label}
            </NavLink>
          ))}

          <div className="sb-divider" />

          {NAV.slice(4).map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => `sb-link${isActive ? " active" : ""}`}
            >
              {item.icon}
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* Logout */}
        <div className="sb-bottom">
          <button className="sb-logout" onClick={handleLogout}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
              <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/>
              <polyline points="16 17 21 12 16 7"/>
              <line x1="21" y1="12" x2="9" y2="12"/>
            </svg>
            Log out
          </button>
        </div>
      </aside>
    </>
  );
}