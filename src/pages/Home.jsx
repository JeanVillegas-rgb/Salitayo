import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Sidebar from "../components/Sidebar";

import {
  getPassages,
  uploadPassage,
  deletePassage
} from "../services/api";

export default function Home() {
  const navigate = useNavigate();

  // ── state ─────────────────────────────────────────
  const [passages, setPassages] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);

  const [text, setText] = useState("");
  const [fileName, setFileName] = useState("");
  const [filter, setFilter] = useState("all");
  const [savedText, setSavedText] = useState(""); // tracks what's already been saved

  const [dragging, setDragging] = useState(false);
  const fileRef = useRef(null);

  const user = JSON.parse(localStorage.getItem("user") || "{}");

  const hour = new Date().getHours();
  const greeting =
    hour < 12 ? "Good morning" :
    hour < 17 ? "Good afternoon" :
    "Good evening";

  // is the current text unsaved? (non-empty, no file, and different from last save)
  const isUnsavedText = text.trim() && !fileName && text !== savedText;

  // ── fetch passages ─────────────────────────────────
  useEffect(() => {
    fetchPassages();
  }, []);

  const fetchPassages = async () => {
    try {
      const res = await getPassages();
      setPassages(res.data.passages);
    } catch (err) {
      console.error(err);
    }
  };

  // ── save raw typed/pasted text ─────────────────────
  const handleSaveText = async () => {
    if (!text.trim()) return;

    setUploading(true);
    setUploadError(null);

    // build a title from the first ~40 chars
    const autoTitle =
      text.trim().split("\n")[0].slice(0, 40) +
      (text.trim().split("\n")[0].length > 40 ? "…" : "");

    const formData = new FormData();
    const blob = new Blob([text], { type: "text/plain" });
    formData.append("file", blob, `${autoTitle}.txt`);
    formData.append("title", autoTitle);

    try {
      await uploadPassage(formData);
      setSavedText(text); // mark as saved
      await fetchPassages();
    } catch (err) {
      console.error(err);
      setUploadError("Save failed.");
    }

    setUploading(false);
  };

  // ── upload file to backend ─────────────────────────
  const handleFile = async (file) => {
    if (!file) return;

    setUploading(true);
    setUploadError(null);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("title", file.name);

    try {
      await uploadPassage(formData);

      const reader = new FileReader();
      reader.onload = (e) => {
        setText(e.target.result);
        setFileName(file.name);
        setSavedText(e.target.result); // files are auto-saved
      };
      reader.readAsText(file);

      await fetchPassages();
    } catch (err) {
      console.error(err);
      setUploadError("Upload failed.");
    }

    setUploading(false);
  };

  // ── drag drop ──────────────────────────────────────
  const onDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    handleFile(e.dataTransfer.files[0]);
  };

  // ── delete ─────────────────────────────────────────
  const handleDelete = async (id) => {
    if (!window.confirm("Delete this passage?")) return;

    try {
      await deletePassage(id);
      fetchPassages();
    } catch (err) {
      console.error(err);
    }
  };

  // ── open passage in writing ────────────────────────
  const openPassage = (p) => {
    sessionStorage.setItem("selectedPassageId", p.id);
    navigate("/writing");
  };

  // ── send raw text to modules ───────────────────────
  const goToModule = (route) => {
    if (!text.trim()) {
      alert("No text to send.");
      return;
    }

    sessionStorage.setItem("importedText", text);
    sessionStorage.setItem("importedFileName", fileName || "");

    navigate(route);
  };


  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,wght@0,300;0,400;1,300;1,400&family=DM+Sans:wght@300;400;500&display=swap');

        :root {
          --cream:  #F7F2EA;
          --sand:   #EDE5D6;
          --stone:  #D4C9B5;
          --moss:   #3D4A2E;
          --fern:   #5C6E42;
          --clay:   #B85C38;
          --rust:   #8C3D1F;
          --terra:  #D4845A;
          --blush:  #E8C4BA;
          --nude:   #F0D8D0;
          --ink:    #1C1A14;
          --muted:  #6B6356;
          --hint:   #A09480;
          --white:  #FFFFFF;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: var(--cream); font-family: 'DM Sans', sans-serif; }

        .app-layout { display: flex; min-height: 100vh; }
        .app-main   { margin-left: 240px; flex: 1; min-height: 100vh; }

        /* ── Page shell ── */
        .home-page {
          padding: 2.5rem 2.75rem;
          max-width: 860px;
        }

        /* ── Greeting ── */
        .greeting {
          margin-bottom: 2rem;
        }
        .greeting-sub {
          font-size: 0.8rem;
          text-transform: uppercase;
          letter-spacing: 0.1em;
          color: var(--clay);
          font-weight: 500;
          margin-bottom: 0.3rem;
        }
        .greeting-name {
          font-family: 'Fraunces', serif;
          font-size: 2rem;
          font-weight: 300;
          color: var(--ink);
          line-height: 1.2;
        }
        .greeting-name i { font-style: italic; color: var(--clay); }
        .greeting-hint {
          font-size: 0.875rem;
          color: var(--muted);
          margin-top: 0.3rem;
          font-weight: 300;
        }

        /* ── Import box ── */
        .import-section { margin-bottom: 2.5rem; }

        .import-box {
          background: white;
          border: 1.5px dashed var(--stone);
          border-radius: 16px;
          padding: 1.5rem;
          transition: border-color 0.2s, background 0.2s;
          cursor: text;
        }
        .import-box.drag-over {
          border-color: var(--clay);
          background: var(--nude);
        }
        .import-box.has-text {
          border-style: solid;
          border-color: var(--stone);
          cursor: default;
        }

        .import-topbar {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 0.875rem;
        }
        .import-label {
          font-size: 0.72rem;
          text-transform: uppercase;
          letter-spacing: 0.08em;
          color: var(--muted);
          font-weight: 500;
        }
        .import-actions { display: flex; gap: 0.5rem; align-items: center; }

        .import-btn {
          padding: 5px 13px;
          border-radius: 100px;
          font-size: 0.78rem;
          font-family: 'DM Sans', sans-serif;
          cursor: pointer;
          transition: all 0.18s;
          border: 1.5px solid var(--stone);
          background: transparent;
          color: var(--muted);
        }
        .import-btn:hover { border-color: var(--clay); color: var(--clay); }
        .import-btn.primary {
          background: var(--clay);
          border-color: var(--clay);
          color: white;
        }
        .import-btn.primary:hover { background: var(--rust); border-color: var(--rust); }
        .import-btn:disabled { opacity: 0.4; cursor: not-allowed; }

        .import-textarea {
          width: 100%;
          min-height: 130px;
          border: none;
          outline: none;
          resize: none;
          font-family: 'DM Sans', sans-serif;
          font-size: 0.95rem;
          line-height: 1.75;
          color: var(--ink);
          background: transparent;
          letter-spacing: 0.01em;
        }
        .import-textarea::placeholder { color: var(--hint); }

        .import-drop-hint {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          font-size: 0.78rem;
          color: var(--hint);
          margin-top: 0.875rem;
          padding-top: 0.875rem;
          border-top: 1px solid var(--sand);
        }
        .import-drop-hint svg { flex-shrink: 0; }

        .filename-badge {
          display: inline-flex;
          align-items: center;
          gap: 0.4rem;
          background: var(--sand);
          border: 1px solid var(--stone);
          border-radius: 100px;
          padding: 3px 10px;
          font-size: 0.75rem;
          color: var(--muted);
          margin-bottom: 0.5rem;
        }

        /* ── Unsaved indicator ── */
        .unsaved-bar {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-top: 0.75rem;
          padding: 0.5rem 0.75rem;
          background: var(--nude);
          border: 1px solid var(--blush);
          border-radius: 10px;
          font-size: 0.8rem;
          color: var(--clay);
        }
        .unsaved-bar span { font-weight: 300; }
        .save-text-btn {
          padding: 4px 14px;
          border-radius: 100px;
          font-size: 0.78rem;
          font-family: 'DM Sans', sans-serif;
          cursor: pointer;
          border: 1.5px solid var(--clay);
          background: var(--clay);
          color: white;
          transition: all 0.18s;
        }
        .save-text-btn:hover { background: var(--rust); border-color: var(--rust); }
        .save-text-btn:disabled { opacity: 0.4; cursor: not-allowed; }

        /* ── Module send buttons ── */
        .module-btns {
          display: flex;
          gap: 0.625rem;
          margin-top: 1rem;
          flex-wrap: wrap;
        }
        .module-btn {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          padding: 8px 16px;
          border-radius: 100px;
          border: 1.5px solid var(--stone);
          background: white;
          font-size: 0.83rem;
          font-family: 'DM Sans', sans-serif;
          color: var(--muted);
          cursor: pointer;
          transition: all 0.18s;
        }
        .module-btn:hover:not(:disabled) {
          border-color: var(--clay);
          color: var(--clay);
          background: var(--nude);
        }
        .module-btn:disabled { opacity: 0.35; cursor: not-allowed; }
        .module-btn svg { flex-shrink: 0; }

        /* ── History ── */
        .history-section {}
        .history-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 1rem;
        }
        .history-title {
          font-family: 'Fraunces', serif;
          font-size: 1.1rem;
          font-weight: 300;
          color: var(--ink);
        }
        .history-title i { font-style: italic; }

        .filter-tabs {
          display: flex;
          gap: 4px;
          background: var(--sand);
          border-radius: 100px;
          padding: 3px;
        }
        .filter-tab {
          padding: 4px 12px;
          border-radius: 100px;
          border: none;
          background: transparent;
          font-size: 0.78rem;
          font-family: 'DM Sans', sans-serif;
          color: var(--muted);
          cursor: pointer;
          transition: all 0.18s;
        }
        .filter-tab.active {
          background: white;
          color: var(--ink);
          font-weight: 500;
          box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        }

        .history-list {
          display: flex;
          flex-direction: column;
          gap: 0.625rem;
        }

        .history-card {
          background: white;
          border: 1px solid var(--stone);
          border-radius: 14px;
          padding: 1rem 1.25rem;
          cursor: pointer;
          transition: all 0.18s;
          display: flex;
          align-items: flex-start;
          gap: 1rem;
        }
        .history-card:hover {
          border-color: var(--clay);
          box-shadow: 0 2px 12px rgba(184,92,56,0.08);
          transform: translateY(-1px);
        }

        .history-icon {
          width: 36px;
          height: 36px;
          border-radius: 10px;
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
          margin-top: 1px;
        }

        .history-body { flex: 1; min-width: 0; }
        .history-card-top {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 0.5rem;
          margin-bottom: 0.25rem;
        }
        .history-card-title {
          font-size: 0.92rem;
          font-weight: 500;
          color: var(--ink);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .history-date {
          font-size: 0.75rem;
          color: var(--hint);
          flex-shrink: 0;
        }
        .history-type-badge {
          display: inline-block;
          font-size: 0.68rem;
          font-weight: 500;
          text-transform: uppercase;
          letter-spacing: 0.07em;
          padding: 2px 8px;
          border-radius: 100px;
          margin-bottom: 0.375rem;
        }
        .history-preview {
          font-size: 0.82rem;
          color: var(--muted);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          font-weight: 300;
          line-height: 1.5;
        }

        .empty-state {
          text-align: center;
          padding: 3rem 1rem;
          color: var(--hint);
        }
        .empty-state svg { margin-bottom: 0.75rem; opacity: 0.4; }
        .empty-state p { font-size: 0.88rem; font-weight: 300; }

        @media (max-width: 768px) {
          .app-main { margin-left: 0; }
          .home-page { padding: 1.5rem; }
        }
      `}</style>

       <div className="app-layout">
      <Sidebar />

      <main className="app-main">
        <div className="home-page">

          {/* ── Greeting ── */}
          <div className="greeting">
            <div className="greeting-sub">{greeting}</div>
            <div className="greeting-name">
              {user.display_name || "there"}<i>,</i>
            </div>
            <div className="greeting-hint">
              Paste or upload a text to get started — then send it to any module below.
            </div>
          </div>

          {/* ── Import box ── */}
          <div className="import-section">
            <div
              className={`import-box ${dragging ? "drag-over" : ""} ${text ? "has-text" : ""}`}
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={onDrop}
            >
              <div className="import-topbar">
                <span className="import-label">
                  {fileName ? "Imported file" : "Your text"}
                </span>

                <div className="import-actions">
                  {text && (
                    <button
                      className="import-btn"
                      onClick={() => { setText(""); setFileName(""); setSavedText(""); }}
                    >
                      Clear
                    </button>
                  )}

                  <button
                    className="import-btn"
                    onClick={() => fileRef.current?.click()}
                  >
                    {uploading ? "Uploading..." : "Upload file"}
                  </button>

                  <input
                    ref={fileRef}
                    type="file"
                    accept=".txt,.doc,.docx,.pdf"
                    style={{ display: "none" }}
                    onChange={(e) => handleFile(e.target.files[0])}
                  />
                </div>
              </div>

              {fileName && (
                <div className="filename-badge">
                  {fileName}
                </div>
              )}

              <textarea
                className="import-textarea"
                placeholder="Paste or type text here, or drag and drop a file above..."
                value={text}
                onChange={(e) => setText(e.target.value)}
              />

              {!text && (
                <div className="import-drop-hint">
                  Drag & drop a file here
                </div>
              )}
            </div>

            {/* Unsaved text nudge — only shows for typed/pasted text */}
            {isUnsavedText && (
              <div className="unsaved-bar">
                <span>This text hasn't been saved to your imports yet.</span>
                <button
                  className="save-text-btn"
                  onClick={handleSaveText}
                  disabled={uploading}
                >
                  {uploading ? "Saving…" : "Save to imports"}
                </button>
              </div>
            )}

            {uploadError && (
              <p style={{ color: "var(--error)", fontSize: "0.8rem", marginTop: "0.5rem" }}>{uploadError}</p>
            )}

            {/* Module buttons */}
            <div className="module-btns">
              <button
                className="module-btn"
                disabled={!text.trim()}
                onClick={() => goToModule("/reading")}
              >
                Send to Reading Restructurer
              </button>

              <button
                className="module-btn"
                disabled={!text.trim()}
                onClick={() => goToModule("/writing")}
              >
                Send to Writing Assistant
              </button>

              <button
                className="module-btn"
                disabled={!text.trim()}
                onClick={() => goToModule("/wordproficiency")}
              >
                Send to Word Proficiency
              </button>
            </div>
          </div>

          {/* ── History ── */}
          <div className="history-section">
            <div className="history-header">
              <div className="history-title">Your Imports<i>.</i></div>
            </div>

            <div className="history-list">
              {passages.length === 0 ? (
                <div className="empty-state">
                  <p>No imports yet.</p>
                </div>
              ) : (
                passages.map((p) => (
                  <div
                    key={p.id}
                    className="history-card"
                    onClick={() => openPassage(p)}
                  >
                    <div className="history-body">
                      <div className="history-card-top">
                        <span className="history-card-title">{p.title}</span>
                        <span className="history-date">
                          {new Date(p.uploaded_at).toLocaleDateString()}
                        </span>
                      </div>

                      <div className="history-preview">
                        {p.content?.slice(0, 100)}...
                      </div>
                    </div>

                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(p.id);
                      }}
                      style={{
                        background: "none",
                        border: "none",
                        color: "var(--error)",
                        cursor: "pointer",
                        fontSize: "0.75rem"
                      }}
                    >
                      Delete
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>

        </div>
      </main>
    </div>
    </>
  );
}