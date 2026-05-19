// pages/WordProficiency.jsx
// Page wrapper at /wordproficiency — shell layout + session resume check.

import { useState, useEffect } from "react";
import Sidebar from "../components/Sidebar";
import { wpGetSessionStatus } from "../services/api";
import WordProficiency from "../components/WordProficiency";

export default function WordProficiencyPage() {
  const [resumeState, setResumeState] = useState(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    wpGetSessionStatus().then(({ data }) => {
      if (data?.active) setResumeState(data);
      setChecking(false);
    });
  }, []);

  return (
    <>
      <style>{`
        .wp-page {
          flex: 1;
          width: 100%;
          min-height: 100vh;
        }
        .wp-page-inner {
          max-width: 720px;
          margin: 0 auto;
          padding: 2.5rem 2rem 3rem;
        }
        .wp-loading {
          display: flex;
          justify-content: center;
          align-items: center;
          min-height: 50vh;
          color: var(--hint);
          font-style: italic;
        }
        @media (max-width: 768px) {
          .wp-page-inner { padding: 1.5rem 1rem 2rem; }
        }
      `}</style>

      <div className="app-layout">
        <Sidebar />

        <main className="app-main wp-page">
          <div className="wp-page-inner">
            {checking ? (
              <p className="wp-loading">Loading…</p>
            ) : (
              <WordProficiency
                resumeState={resumeState}
                onResumeConsumed={() => setResumeState(null)}
              />
            )}
          </div>
        </main>
      </div>
    </>
  );
}
