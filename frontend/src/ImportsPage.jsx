import { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import './ImportsPage.css'

export default function ImportsPage({ onBack }) {
  const [passages, setPassages] = useState([])
  const [file, setFile] = useState(null)
  const [title, setTitle] = useState('')
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState(null)
  const [uploadSuccess, setUploadSuccess] = useState(null)
  const [deletingId, setDeletingId] = useState(null)
  const fileInputRef = useRef(null)

  const API = "/api"

  const fetchPassages = () => {
    axios.get(`${API}/passages/`)
      .then(res => setPassages(res.data.passages))
      .catch(err => console.error('Failed to fetch passages:', err))
  }

  useEffect(() => {
    fetchPassages()
  }, [])

  const handleUpload = async () => {
    if (!file) return
    setUploading(true)
    setUploadError(null)
    setUploadSuccess(null)

    const formData = new FormData()
    formData.append('file', file)
    formData.append('title', title || file.name)

    try {
      const res = await axios.post(`${API}/passages/extract/`, formData)
      const msg = res.data.truncated
        ? `"${res.data.title}" saved (truncated to 3 000 words).`
        : `"${res.data.title}" saved successfully.`
      setUploadSuccess(msg)
      setFile(null)
      setTitle('')
      if (fileInputRef.current) fileInputRef.current.value = ''
      fetchPassages()
    } catch (err) {
      const msg = err.response?.data?.error || 'Failed to extract text from file.'
      setUploadError(msg)
    } finally {
      setUploading(false)
    }
  }

  const handleDelete = async (id, passageTitle) => {
    if (!window.confirm(`Delete "${passageTitle}"?`)) return
    setDeletingId(id)
    try {
      await axios.delete(`${API}/passages/${id}/delete/`)
      setPassages(prev => prev.filter(p => p.id !== id))
    } catch (err) {
      console.error('Delete failed:', err)
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="imports-page">
      <div className="imports-topbar">
        <button className="imports-back-btn" onClick={onBack}>
          ΓåÉ Back to Writing Coach
        </button>
      </div>

      <div className="imports-content">
        <div className="imports-header">
          <h1>Reference Passages</h1>
          <p className="imports-subtitle">
            Upload PDF or DOCX files to save them as reference passages. Passages are stored
            and available for future sessions.
          </p>
        </div>

        {/* Upload box */}
        <div className="upload-box">
          <h2>Upload New File</h2>

          <label className="upload-field-label">Title (optional)</label>
          <input
            type="text"
            className="upload-title-input"
            placeholder="e.g. Chapter 3 ΓÇö Reading Comprehension"
            value={title}
            onChange={e => setTitle(e.target.value)}
          />

          <label className="upload-field-label">File</label>
          <div className="file-row">
            <label className="file-choose-btn">
              {file ? file.name : 'Choose PDF or DOCXΓÇª'}
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx"
                onChange={e => {
                  setFile(e.target.files[0] || null)
                  setUploadError(null)
                  setUploadSuccess(null)
                }}
                hidden
              />
            </label>
            {file && (
              <button
                className="file-clear-btn"
                onClick={() => {
                  setFile(null)
                  if (fileInputRef.current) fileInputRef.current.value = ''
                }}
              >
                Γ£ò
              </button>
            )}
          </div>

          <button
            className="upload-btn"
            onClick={handleUpload}
            disabled={!file || uploading}
          >
            {uploading ? 'UploadingΓÇª' : 'Upload'}
          </button>

          {uploadSuccess && <p className="upload-success">{uploadSuccess}</p>}
          {uploadError && <p className="upload-error">{uploadError}</p>}
        </div>

        {/* Saved passages */}
        <div className="passages-section">
          <h2>Saved Passages ({passages.length})</h2>

          {passages.length === 0 ? (
            <div className="passages-empty">
              No passages uploaded yet. Upload a PDF or DOCX above.
            </div>
          ) : (
            <div className="passages-list">
              {passages.map(p => (
                <div key={p.id} className="passage-card">
                  <div className="passage-info">
                    <span className="passage-title">{p.title}</span>
                    <span className="passage-date">
                      {new Date(p.uploaded_at).toLocaleDateString(undefined, {
                        year: 'numeric', month: 'short', day: 'numeric',
                      })}
                    </span>
                  </div>
                  <button
                    className="passage-delete-btn"
                    onClick={() => handleDelete(p.id, p.title)}
                    disabled={deletingId === p.id}
                  >
                    {deletingId === p.id ? 'ΓÇª' : 'Delete'}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
