import { useEffect, useState } from 'react'

interface HealthResponse {
  status: string
  database?: string
  version?: string
}

type ConnectionStatus = 'connecting' | 'connected' | 'error'

interface Repository {
  id: string
  name: string
  owner: string
  url: string
  default_branch: string
  description?: string | null
  language?: string | null
  status: 'pending' | 'ingesting' | 'completed' | 'failed'
  created_at: string
  updated_at: string
  file_count: number
}

interface ScannedFile {
  id: string
  path: string
  language?: string | null
  size_bytes?: number | null
  content_hash?: string | null
}

interface FileListResponse {
  total: number
  limit: number
  offset: number
  files: ScannedFile[]
}

export function App() {
  // System Health State
  const [status, setStatus] = useState<ConnectionStatus>('connecting')
  const [healthData, setHealthData] = useState<HealthResponse | null>(null)
  const [lastChecked, setLastChecked] = useState<string | null>(null)

  // Repository Ingestion State
  const [repoUrlInput, setRepoUrlInput] = useState('')
  const [isImporting, setIsImporting] = useState(false)
  const [importError, setImportError] = useState<string | null>(null)

  const [repositories, setRepositories] = useState<Repository[]>([])
  const [isLoadingRepos, setIsLoadingRepos] = useState(false)
  const [ingestingRepoId, setIngestingRepoId] = useState<string | null>(null)
  const [repoActionError, setRepoActionError] = useState<{ [key: string]: string }>({})

  // File Preview State
  const [expandedRepoId, setExpandedRepoId] = useState<string | null>(null)
  const [repoFiles, setRepoFiles] = useState<{ [key: string]: ScannedFile[] }>({})
  const [isLoadingFiles, setIsLoadingFiles] = useState(false)
  const [fileSearchTerm, setFileSearchTerm] = useState('')

  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

  const checkHealth = async () => {
    setStatus('connecting')
    try {
      const response = await fetch(`${apiBaseUrl}/health`)
      if (!response.ok) {
        throw new Error(`HTTP error ${response.status}: ${response.statusText}`)
      }
      const data: HealthResponse = await response.json()
      if (data.status === 'ok') {
        setHealthData(data)
        setStatus('connected')
      } else {
        throw new Error(`Unexpected status payload: ${JSON.stringify(data)}`)
      }
    } catch {
      setStatus('error')
    } finally {
      setLastChecked(new Date().toLocaleTimeString())
    }
  }

  const fetchRepositories = async () => {
    setIsLoadingRepos(true)
    try {
      const response = await fetch(`${apiBaseUrl}/repositories`)
      if (response.ok) {
        const data: Repository[] = await response.json()
        setRepositories(data)
      }
    } catch (err) {
      console.error('Failed to fetch repositories:', err)
    } finally {
      setIsLoadingRepos(false)
    }
  }

  useEffect(() => {
    checkHealth()
    fetchRepositories()
  }, [])

  const handleImportSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setImportError(null)

    const trimmedUrl = repoUrlInput.trim()
    if (!trimmedUrl) {
      setImportError('Please enter a GitHub repository URL.')
      return
    }

    setIsImporting(true)
    try {
      const res = await fetch(`${apiBaseUrl}/repositories`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: trimmedUrl }),
      })

      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || 'Failed to import repository.')
      }

      setRepoUrlInput('')
      await fetchRepositories()
    } catch (err: unknown) {
      setImportError(err instanceof Error ? err.message : 'Import failed')
    } finally {
      setIsImporting(false)
    }
  }

  const handleTriggerIngestion = async (repoId: string) => {
    setIngestingRepoId(repoId)
    setRepoActionError((prev) => ({ ...prev, [repoId]: '' }))

    // Optimistically update status to ingesting in UI
    setRepositories((prev) =>
      prev.map((r) => (r.id === repoId ? { ...r, status: 'ingesting' } : r))
    )

    try {
      const res = await fetch(`${apiBaseUrl}/repositories/${repoId}/ingest`, {
        method: 'POST',
      })
      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || 'Ingestion failed.')
      }

      // Refresh repository details and files
      await fetchRepositories()
      if (expandedRepoId === repoId) {
        await loadRepositoryFiles(repoId)
      }
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : 'Ingestion failed'
      setRepoActionError((prev) => ({ ...prev, [repoId]: errMsg }))
      await fetchRepositories()
    } finally {
      setIngestingRepoId(null)
    }
  }

  const loadRepositoryFiles = async (repoId: string) => {
    setIsLoadingFiles(true)
    try {
      const res = await fetch(`${apiBaseUrl}/repositories/${repoId}/files?limit=100`)
      if (res.ok) {
        const data: FileListResponse = await res.json()
        setRepoFiles((prev) => ({ ...prev, [repoId]: data.files }))
      }
    } catch (err) {
      console.error('Failed to load files:', err)
    } finally {
      setIsLoadingFiles(false)
    }
  }

  const toggleExpandFiles = async (repoId: string) => {
    if (expandedRepoId === repoId) {
      setExpandedRepoId(null)
      setFileSearchTerm('')
    } else {
      setExpandedRepoId(repoId)
      setFileSearchTerm('')
      if (!repoFiles[repoId]) {
        await loadRepositoryFiles(repoId)
      }
    }
  }

  const formatFileSize = (bytes?: number | null) => {
    if (bytes === undefined || bytes === null) return '0 B'
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
  }

  return (
    <main className="card" id="main-card">
      {/* Brand Header */}
      <header className="header">
        <div className="logo-badge" aria-hidden="true">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <circle cx="12" cy="12" r="10" />
            <circle cx="12" cy="12" r="4" />
            <line x1="4.93" y1="4.93" x2="9.17" y2="9.17" />
            <line x1="14.83" y1="14.83" x2="19.07" y2="19.07" />
            <line x1="14.83" y1="9.17" x2="19.07" y2="4.93" />
            <line x1="4.93" y1="14.83" x2="9.17" y2="19.07" />
          </svg>
        </div>
        <div>
          <h1 id="app-title">CodeLens</h1>
          <p className="subtitle">AI-Powered Codebase Intelligence Platform</p>
        </div>
      </header>

      {/* Backend System Health Status Banner */}
      <section className={`status-box status-${status}`} id="connection-status-container">
        <div className="status-info">
          <div className="pulse-indicator" aria-hidden="true">
            <div className="pulse-dot" />
            <div className="pulse-ring" />
          </div>
          <div className="status-text" id="status-display">
            {status === 'connected' && `Backend Connected (v${healthData?.version || '0.1.0'})`}
            {status === 'connecting' && 'Connecting to Backend...'}
            {status === 'error' && 'Backend Connection Failed'}
          </div>
        </div>
        <div className="header-actions">
          <span className="endpoint-badge">GET /health</span>
          <button
            id="btn-recheck"
            className="btn btn-secondary btn-sm"
            onClick={checkHealth}
            disabled={status === 'connecting'}
            title="Refresh backend status"
          >
            {status === 'connecting' ? 'Checking...' : 'Refresh'}
          </button>
        </div>
      </section>

      {/* Section 1: Ingestion Form */}
      <section className="section-block" id="import-section">
        <div className="section-header">
          <h2 className="section-title">Import GitHub Repository</h2>
          <span className="section-subtitle">
            Ingest and scan source code structure into CodeLens
          </span>
        </div>

        <form onSubmit={handleImportSubmit} className="import-form" id="repo-import-form">
          <div className="input-wrapper">
            <svg
              className="input-icon"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22" />
            </svg>
            <input
              id="repo-url-input"
              type="text"
              className="text-input"
              placeholder="https://github.com/owner/repository"
              value={repoUrlInput}
              onChange={(e) => setRepoUrlInput(e.target.value)}
              disabled={isImporting}
            />
          </div>
          <button
            id="btn-import-repo"
            type="submit"
            className="btn btn-primary"
            disabled={isImporting || !repoUrlInput.trim()}
          >
            {isImporting ? (
              <>
                <span className="spinner" />
                <span>Importing...</span>
              </>
            ) : (
              'Import Repository'
            )}
          </button>
        </form>

        {importError && (
          <div className="alert alert-error" id="import-error-banner">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            <span>{importError}</span>
          </div>
        )}
      </section>

      {/* Section 2: Repositories List */}
      <section className="section-block" id="repositories-section">
        <div className="section-header-row">
          <div>
            <h2 className="section-title">Tracked Repositories</h2>
            <span className="section-subtitle">
              {repositories.length} {repositories.length === 1 ? 'repository' : 'repositories'} in database
            </span>
          </div>
          <button
            className="btn btn-icon"
            onClick={fetchRepositories}
            disabled={isLoadingRepos}
            title="Refresh repository list"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M23 4v6h-6" />
              <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
            </svg>
          </button>
        </div>

        {repositories.length === 0 ? (
          <div className="empty-state" id="empty-repositories-state">
            <div className="empty-icon">📁</div>
            <p className="empty-text">No repositories imported yet.</p>
            <p className="empty-hint">Enter a public GitHub repository URL above to get started.</p>
          </div>
        ) : (
          <div className="repo-list" id="repositories-list">
            {repositories.map((repo) => {
              const isIngesting = ingestingRepoId === repo.id || repo.status === 'ingesting'
              const isExpanded = expandedRepoId === repo.id
              const files = repoFiles[repo.id] || []
              const filteredFiles = fileSearchTerm
                ? files.filter((f) =>
                    f.path.toLowerCase().includes(fileSearchTerm.toLowerCase())
                  )
                : files

              return (
                <div key={repo.id} className="repo-card" id={`repo-card-${repo.id}`}>
                  <div className="repo-card-top">
                    <div className="repo-info">
                      <div className="repo-title-row">
                        <span className="repo-owner">{repo.owner} /</span>
                        <h3 className="repo-name">{repo.name}</h3>
                        <span className={`status-pill pill-${repo.status}`}>
                          {repo.status === 'ingesting' && <span className="pill-dot" />}
                          {repo.status}
                        </span>
                      </div>
                      <a
                        href={repo.url}
                        target="_blank"
                        rel="noreferrer"
                        className="repo-link"
                      >
                        {repo.url}
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                          <polyline points="15 3 21 3 21 9" />
                          <line x1="10" y1="14" x2="21" y2="3" />
                        </svg>
                      </a>
                    </div>

                    <div className="repo-actions">
                      <button
                        className="btn btn-primary btn-sm"
                        onClick={() => handleTriggerIngestion(repo.id)}
                        disabled={isIngesting}
                        id={`btn-ingest-${repo.id}`}
                      >
                        {isIngesting ? (
                          <>
                            <span className="spinner spinner-sm" />
                            <span>Ingesting...</span>
                          </>
                        ) : repo.status === 'completed' ? (
                          'Re-ingest'
                        ) : (
                          'Start Ingestion'
                        )}
                      </button>

                      {repo.file_count > 0 && (
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => toggleExpandFiles(repo.id)}
                          id={`btn-toggle-files-${repo.id}`}
                        >
                          {isExpanded ? 'Hide Files' : `View Files (${repo.file_count})`}
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Metadata Row */}
                  <div className="repo-stats">
                    <div className="stat-item">
                      <span className="stat-label">Files Indexed</span>
                      <span className="stat-value">{repo.file_count}</span>
                    </div>
                    {repo.language && (
                      <div className="stat-item">
                        <span className="stat-label">Language</span>
                        <span className="stat-value">{repo.language}</span>
                      </div>
                    )}
                    <div className="stat-item">
                      <span className="stat-label">Default Branch</span>
                      <span className="stat-value font-mono">{repo.default_branch}</span>
                    </div>
                  </div>

                  {/* Action Error Message */}
                  {repoActionError[repo.id] && (
                    <div className="alert alert-error alert-compact">
                      <span>{repoActionError[repo.id]}</span>
                    </div>
                  )}

                  {/* Expanded File Explorer */}
                  {isExpanded && (
                    <div className="file-preview-container">
                      <div className="file-search-bar">
                        <input
                          type="text"
                          className="search-input"
                          placeholder="Filter files by path..."
                          value={fileSearchTerm}
                          onChange={(e) => setFileSearchTerm(e.target.value)}
                        />
                        <span className="file-count-label">
                          Showing {filteredFiles.length} of {repo.file_count} files
                        </span>
                      </div>

                      {isLoadingFiles ? (
                        <div className="loading-state">
                          <span className="spinner" />
                          <span>Loading repository files...</span>
                        </div>
                      ) : filteredFiles.length === 0 ? (
                        <div className="empty-files">No files match your search filter.</div>
                      ) : (
                        <div className="file-table-wrapper">
                          <table className="file-table">
                            <thead>
                              <tr>
                                <th>Path</th>
                                <th>Language</th>
                                <th>Size</th>
                                <th>SHA-256 Hash</th>
                              </tr>
                            </thead>
                            <tbody>
                              {filteredFiles.slice(0, 100).map((file) => (
                                <tr key={file.id}>
                                  <td className="file-path font-mono">{file.path}</td>
                                  <td>
                                    {file.language ? (
                                      <span className="tag-lang">{file.language}</span>
                                    ) : (
                                      <span className="tag-plain">—</span>
                                    )}
                                  </td>
                                  <td className="file-size font-mono">
                                    {formatFileSize(file.size_bytes)}
                                  </td>
                                  <td className="file-hash font-mono" title={file.content_hash || ''}>
                                    {file.content_hash ? file.content_hash.slice(0, 10) + '...' : '—'}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </section>

      {/* Footer */}
      <footer className="footer">
        {lastChecked && <span>System verified: {lastChecked}</span>}
      </footer>
    </main>
  )
}

export default App
