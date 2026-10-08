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

interface SymbolItem {
  id: string
  name: string
  kind: string
  file_id: string
  file_path?: string
  signature?: string | null
  docstring?: string | null
  line_start: number
  line_end: number
}

interface SymbolListResponse {
  total: number
  symbols: SymbolItem[]
}

interface DependencyNode {
  id: string
  label: string
  type: string
  language?: string | null
}

interface DependencyEdge {
  source: string
  target: string
  type: string
  symbol_name?: string | null
}

interface DependencyGraphResponse {
  repository_id: string
  nodes: DependencyNode[]
  edges: DependencyEdge[]
  total_dependencies: number
}

interface ImpactReport {
  target: string
  target_type: string
  direct_dependents: string[]
  indirect_dependents: string[]
  affected_files: string[]
  impact_level: string
  summary: string
}

interface QueryCitation {
  file_path: string
  start_line: number
  end_line: number
  symbol_name?: string | null
  snippet: string
}

interface QueryResponse {
  question: string
  answer: string
  citations: QueryCitation[]
  related_symbols: string[]
  confidence: number
}

type ActiveTab = 'files' | 'symbols' | 'dependencies' | 'impact' | 'qa'

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

  // Active Repository & Tab Selection
  const [activeRepoId, setActiveRepoId] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<ActiveTab>('files')

  // Expanded File Preview State (backwards compatible)
  const [expandedRepoId, setExpandedRepoId] = useState<string | null>(null)
  const [repoFiles, setRepoFiles] = useState<{ [key: string]: ScannedFile[] }>({})
  const [isLoadingFiles, setIsLoadingFiles] = useState(false)
  const [fileSearchTerm, setFileSearchTerm] = useState('')

  // Code Viewer State
  const [selectedFile, setSelectedFile] = useState<ScannedFile | null>(null)
  const [fileContent, setFileContent] = useState<string>('')
  const [isLoadingContent, setIsLoadingContent] = useState(false)

  // AST Symbols State
  const [symbols, setSymbols] = useState<SymbolItem[]>([])
  const [isLoadingSymbols, setIsLoadingSymbols] = useState(false)
  const [symbolKindFilter, setSymbolKindFilter] = useState<string>('all')
  const [symbolSearch, setSymbolSearch] = useState<string>('')

  // Dependency Graph State
  const [depGraph, setDepGraph] = useState<DependencyGraphResponse | null>(null)
  const [isLoadingDeps, setIsLoadingDeps] = useState(false)
  const [depTypeFilter, setDepTypeFilter] = useState<string>('all')

  // Impact Analysis State
  const [impactTarget, setImpactTarget] = useState<string>('')
  const [impactReport, setImpactReport] = useState<ImpactReport | null>(null)
  const [isLoadingImpact, setIsLoadingImpact] = useState(false)

  // AI Q&A State
  const [questionInput, setQuestionInput] = useState<string>('')
  const [isAsking, setIsAsking] = useState(false)
  const [qaResponse, setQaResponse] = useState<QueryResponse | null>(null)

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
        if (data.length > 0 && !activeRepoId) {
          setActiveRepoId(data[0].id)
        }
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

  // Load files when active repository changes
  useEffect(() => {
    if (activeRepoId) {
      loadRepositoryFiles(activeRepoId)
      loadRepositorySymbols(activeRepoId)
      loadRepositoryDeps(activeRepoId)
    }
  }, [activeRepoId])

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
      setActiveRepoId(data.id)
    } catch (err: unknown) {
      setImportError(err instanceof Error ? err.message : 'Import failed')
    } finally {
      setIsImporting(false)
    }
  }

  const handleTriggerIngestion = async (repoId: string) => {
    setIngestingRepoId(repoId)
    setRepoActionError((prev) => ({ ...prev, [repoId]: '' }))

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

      await fetchRepositories()
      await loadRepositoryFiles(repoId)
      await loadRepositorySymbols(repoId)
      await loadRepositoryDeps(repoId)
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
      const res = await fetch(`${apiBaseUrl}/repositories/${repoId}/files?limit=150`)
      if (res.ok) {
        const data: FileListResponse = await res.json()
        setRepoFiles((prev) => ({ ...prev, [repoId]: data.files }))
        if (data.files.length > 0 && !selectedFile) {
          loadFileContent(repoId, data.files[0])
        }
      }
    } catch (err) {
      console.error('Failed to load files:', err)
    } finally {
      setIsLoadingFiles(false)
    }
  }

  const loadFileContent = async (repoId: string, file: ScannedFile) => {
    setSelectedFile(file)
    setIsLoadingContent(true)
    try {
      const res = await fetch(`${apiBaseUrl}/repositories/${repoId}/files/${file.id}/content`)
      if (res.ok) {
        const data = await res.json()
        setFileContent(data.content)
      } else {
        setFileContent('// Could not load file content.')
      }
    } catch {
      setFileContent('// Error loading file content.')
    } finally {
      setIsLoadingContent(false)
    }
  }

  const loadRepositorySymbols = async (repoId: string) => {
    setIsLoadingSymbols(true)
    try {
      const res = await fetch(`${apiBaseUrl}/repositories/${repoId}/symbols?limit=200`)
      if (res.ok) {
        const data: SymbolListResponse = await res.json()
        setSymbols(data.symbols)
      }
    } catch (err) {
      console.error('Failed to load symbols:', err)
    } finally {
      setIsLoadingSymbols(false)
    }
  }

  const loadRepositoryDeps = async (repoId: string) => {
    setIsLoadingDeps(true)
    try {
      const res = await fetch(`${apiBaseUrl}/repositories/${repoId}/dependencies`)
      if (res.ok) {
        const data: DependencyGraphResponse = await res.json()
        setDepGraph(data)
      }
    } catch (err) {
      console.error('Failed to load dependencies:', err)
    } finally {
      setIsLoadingDeps(false)
    }
  }

  const handleRunImpact = async (target: string) => {
    if (!activeRepoId || !target.trim()) return
    setIsLoadingImpact(true)
    try {
      const res = await fetch(
        `${apiBaseUrl}/repositories/${activeRepoId}/impact?target=${encodeURIComponent(target.trim())}`
      )
      if (res.ok) {
        const data: ImpactReport = await res.json()
        setImpactReport(data)
      }
    } catch (err) {
      console.error('Impact analysis error:', err)
    } finally {
      setIsLoadingImpact(false)
    }
  }

  const handleAskQuestion = async (queryText?: string) => {
    const q = (queryText || questionInput).trim()
    if (!activeRepoId || !q) return
    setIsAsking(true)
    try {
      const res = await fetch(`${apiBaseUrl}/repositories/${activeRepoId}/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q }),
      })
      if (res.ok) {
        const data: QueryResponse = await res.json()
        setQaResponse(data)
      }
    } catch (err) {
      console.error('Ask query error:', err)
    } finally {
      setIsAsking(false)
    }
  }

  const toggleExpandFiles = async (repoId: string) => {
    if (expandedRepoId === repoId) {
      setExpandedRepoId(null)
    } else {
      setExpandedRepoId(repoId)
      setActiveRepoId(repoId)
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

  const currentRepo = repositories.find((r) => r.id === activeRepoId) || repositories[0]
  const currentFiles = activeRepoId ? repoFiles[activeRepoId] || [] : []
  const filteredFiles = fileSearchTerm
    ? currentFiles.filter((f) => f.path.toLowerCase().includes(fileSearchTerm.toLowerCase()))
    : currentFiles

  const filteredSymbols = symbols.filter((s) => {
    const matchesKind = symbolKindFilter === 'all' || s.kind.toLowerCase() === symbolKindFilter
    const matchesSearch = !symbolSearch || s.name.toLowerCase().includes(symbolSearch.toLowerCase())
    return matchesKind && matchesSearch
  })

  const filteredDeps = (depGraph?.edges || []).filter((e) => {
    return depTypeFilter === 'all' || e.type.toLowerCase() === depTypeFilter
  })

  return (
    <main className="card" id="main-card">
      {/* Brand Header */}
      <header className="header">
        <div className="brand-row">
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
            <p className="subtitle">AI-Powered Codebase Intelligence & Reasoning Platform</p>
          </div>
        </div>

        {/* System Health Status Indicator */}
        <div className={`status-box status-${status}`} id="connection-status-container" style={{ margin: 0 }}>
          <div className="status-info">
            <div className="pulse-indicator" aria-hidden="true">
              <div className="pulse-dot" />
              <div className="pulse-ring" />
            </div>
            <div className="status-text" id="status-display">
              {status === 'connected' && `Backend Online (v${healthData?.version || '0.1.0'})`}
              {status === 'connecting' && 'Connecting...'}
              {status === 'error' && 'Connection Failed'}
            </div>
          </div>
          <div className="header-actions">
            <button
              id="btn-recheck"
              className="btn btn-secondary btn-sm"
              onClick={checkHealth}
              disabled={status === 'connecting'}
              title="Refresh backend status"
            >
              {status === 'connecting' ? '...' : 'Refresh'}
            </button>
          </div>
        </div>
      </header>

      {/* Section 1: Ingestion Form */}
      <section className="section-block" id="import-section">
        <div className="section-header">
          <h2 className="section-title">Import & Index GitHub Repository</h2>
          <span className="section-subtitle">
            Parse AST symbols, map cross-file dependencies, and generate intelligent embeddings
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
              {repositories.length} {repositories.length === 1 ? 'repository' : 'repositories'} indexed
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
              const isSelected = activeRepoId === repo.id
              const isExpanded = expandedRepoId === repo.id

              return (
                <div
                  key={repo.id}
                  className={`repo-card ${isSelected ? 'active-repo' : ''}`}
                  id={`repo-card-${repo.id}`}
                >
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
                      <a href={repo.url} target="_blank" rel="noreferrer" className="repo-link">
                        {repo.url}
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
                          'Re-ingest & Parse'
                        ) : (
                          'Start Ingestion'
                        )}
                      </button>

                      <button
                        className={`btn btn-sm ${isSelected ? 'btn-primary' : 'btn-secondary'}`}
                        onClick={() => {
                          setActiveRepoId(repo.id)
                          toggleExpandFiles(repo.id)
                        }}
                        id={`btn-toggle-files-${repo.id}`}
                      >
                        {isSelected && isExpanded ? 'Hide Workspace' : `Explore Codebase (${repo.file_count})`}
                      </button>
                    </div>
                  </div>

                  <div className="repo-stats">
                    <div className="stat-item">
                      <span className="stat-label">Files</span>
                      <span className="stat-value">{repo.file_count}</span>
                    </div>
                    {repo.language && (
                      <div className="stat-item">
                        <span className="stat-label">Primary Language</span>
                        <span className="stat-value">{repo.language}</span>
                      </div>
                    )}
                    <div className="stat-item">
                      <span className="stat-label">Branch</span>
                      <span className="stat-value font-mono">{repo.default_branch}</span>
                    </div>
                  </div>

                  {repoActionError[repo.id] && (
                    <div className="alert alert-error alert-compact">
                      <span>{repoActionError[repo.id]}</span>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </section>

      {/* Section 3: Deep Code Intelligence Workspace */}
      {currentRepo && (
        <section className="tabs-container" id="intelligence-workspace">
          <div className="section-header-row">
            <div>
              <h2 className="section-title">
                Code Intelligence: {currentRepo.owner}/{currentRepo.name}
              </h2>
              <span className="section-subtitle">
                Explore structural AST symbols, dependency graphs, impact predictions, and AI reasoning
              </span>
            </div>
          </div>

          {/* Navigation Tabs */}
          <nav className="tabs-nav">
            <button
              className={`tab-btn ${activeTab === 'files' ? 'active' : ''}`}
              onClick={() => setActiveTab('files')}
            >
              <span>📁 Files & Code</span>
              <span className="tab-badge">{currentFiles.length}</span>
            </button>
            <button
              className={`tab-btn ${activeTab === 'symbols' ? 'active' : ''}`}
              onClick={() => setActiveTab('symbols')}
            >
              <span>🏷️ AST Symbols</span>
              <span className="tab-badge">{symbols.length}</span>
            </button>
            <button
              className={`tab-btn ${activeTab === 'dependencies' ? 'active' : ''}`}
              onClick={() => setActiveTab('dependencies')}
            >
              <span>🕸️ Dependency Graph</span>
              <span className="tab-badge">{depGraph?.edges.length || 0}</span>
            </button>
            <button
              className={`tab-btn ${activeTab === 'impact' ? 'active' : ''}`}
              onClick={() => setActiveTab('impact')}
            >
              <span>⚡ Impact Analysis</span>
            </button>
            <button
              className={`tab-btn ${activeTab === 'qa' ? 'active' : ''}`}
              onClick={() => setActiveTab('qa')}
            >
              <span>🤖 AI Codebase Q&A</span>
            </button>
          </nav>

          {/* TAB 1: File & Code Explorer */}
          {activeTab === 'files' && (
            <div className="explorer-grid">
              <div className="file-sidebar">
                <div className="sidebar-search">
                  <input
                    type="text"
                    className="sidebar-input"
                    placeholder="Filter files by path..."
                    value={fileSearchTerm}
                    onChange={(e) => setFileSearchTerm(e.target.value)}
                  />
                </div>
                {isLoadingFiles ? (
                  <div style={{ padding: '1.5rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                    Loading files...
                  </div>
                ) : filteredFiles.length === 0 ? (
                  <div style={{ padding: '1.5rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                    No files found.
                  </div>
                ) : (
                  <ul className="file-tree-list">
                    {filteredFiles.map((file) => (
                      <li
                        key={file.id}
                        className={`file-tree-item ${selectedFile?.id === file.id ? 'selected' : ''}`}
                        onClick={() => loadFileContent(currentRepo.id, file)}
                      >
                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {file.path}
                        </span>
                        <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                          {formatFileSize(file.size_bytes)}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div className="code-viewer-pane">
                <div className="code-header">
                  <div className="code-title">
                    <span>📄</span>
                    <span>{selectedFile?.path || 'Select a file to inspect'}</span>
                  </div>
                  {selectedFile?.language && (
                    <span className="tag-lang">{selectedFile.language}</span>
                  )}
                </div>
                <div className="code-body">
                  {isLoadingContent ? (
                    <div style={{ color: 'var(--text-muted)' }}>Loading code content...</div>
                  ) : !selectedFile ? (
                    <div style={{ color: 'var(--text-muted)' }}>
                      Select any file from the sidebar to view source code.
                    </div>
                  ) : (
                    <div>
                      {fileContent.split('\n').map((line, idx) => (
                        <div key={idx} className="code-line-row">
                          <span className="line-num">{idx + 1}</span>
                          <span className="line-code">{line || ' '}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: AST Symbols Outline */}
          {activeTab === 'symbols' && (
            <div>
              <div className="filter-bar">
                <div className="filter-pills">
                  {['all', 'function', 'class', 'method', 'interface'].map((k) => (
                    <button
                      key={k}
                      className={`pill-btn ${symbolKindFilter === k ? 'active' : ''}`}
                      onClick={() => setSymbolKindFilter(k)}
                    >
                      {k.toUpperCase()}
                    </button>
                  ))}
                </div>
                <input
                  type="text"
                  className="sidebar-input"
                  style={{ width: '260px' }}
                  placeholder="Search symbols by name..."
                  value={symbolSearch}
                  onChange={(e) => setSymbolSearch(e.target.value)}
                />
              </div>

              {isLoadingSymbols ? (
                <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                  Extracting AST symbols...
                </div>
              ) : filteredSymbols.length === 0 ? (
                <div className="empty-state">
                  <p className="empty-text">No symbols extracted yet.</p>
                  <p className="empty-hint">Trigger ingestion above to extract classes, functions, and methods.</p>
                </div>
              ) : (
                <div className="symbols-grid">
                  {filteredSymbols.map((s) => (
                    <div key={s.id} className="symbol-card">
                      <div className="symbol-header">
                        <span className="symbol-name">{s.name}</span>
                        <span className={`kind-tag kind-${s.kind}`}>{s.kind}</span>
                      </div>
                      {s.signature && (
                        <div className="symbol-sig" title={s.signature}>
                          {s.signature}
                        </div>
                      )}
                      {s.docstring && (
                        <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                          {s.docstring}
                        </p>
                      )}
                      <div className="symbol-meta">
                        <span style={{ fontFamily: 'var(--font-mono)' }}>{s.file_path || 'file'}</span>
                        <span>
                          Lines {s.line_start}–{s.line_end}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* TAB 3: Dependency Graph */}
          {activeTab === 'dependencies' && (
            <div>
              <div className="filter-bar">
                <div className="filter-pills">
                  {['all', 'import', 'call', 'inheritance'].map((t) => (
                    <button
                      key={t}
                      className={`pill-btn ${depTypeFilter === t ? 'active' : ''}`}
                      onClick={() => setDepTypeFilter(t)}
                    >
                      {t.toUpperCase()}
                    </button>
                  ))}
                </div>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                  {filteredDeps.length} directional relationships mapped
                </span>
              </div>

              {isLoadingDeps ? (
                <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                  Mapping dependency relationships...
                </div>
              ) : filteredDeps.length === 0 ? (
                <div className="empty-state">
                  <p className="empty-text">No dependencies mapped yet.</p>
                  <p className="empty-hint">Trigger repository ingestion to resolve import and call graphs.</p>
                </div>
              ) : (
                <div className="dep-matrix-grid">
                  {filteredDeps.map((dep, idx) => (
                    <div key={idx} className="dep-card">
                      <div className="dep-relation-row">
                        <span className="dep-file-badge" title={dep.source}>
                          {dep.source.split('/').pop()}
                        </span>
                        <span style={{ color: 'var(--accent-cyan)' }}>→</span>
                        <span className="dep-file-badge" title={dep.target}>
                          {dep.target.split('/').pop()}
                        </span>
                        <span className="dep-type-pill">{dep.type}</span>
                      </div>
                      {dep.symbol_name && (
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          Referencing symbol:{' '}
                          <span style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                            {dep.symbol_name}
                          </span>
                        </div>
                      )}
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                        {dep.source}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* TAB 4: Impact Analysis */}
          {activeTab === 'impact' && (
            <div className="impact-container">
              <div className="impact-controls">
                <input
                  type="text"
                  className="text-input"
                  placeholder="Enter target file path (e.g. app/main.py) or symbol name..."
                  value={impactTarget}
                  onChange={(e) => setImpactTarget(e.target.value)}
                />
                <button
                  className="btn btn-primary"
                  onClick={() => handleRunImpact(impactTarget)}
                  disabled={isLoadingImpact || !impactTarget.trim()}
                >
                  {isLoadingImpact ? 'Analyzing...' : 'Analyze Impact'}
                </button>
              </div>

              {/* Quick suggestions */}
              <div className="qa-presets-row">
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Quick targets:</span>
                {currentFiles.slice(0, 4).map((f) => (
                  <button
                    key={f.id}
                    className="preset-chip"
                    onClick={() => {
                      setImpactTarget(f.path)
                      handleRunImpact(f.path)
                    }}
                  >
                    {f.path.split('/').pop()}
                  </button>
                ))}
              </div>

              {impactReport && (
                <div className="impact-result-card">
                  <div className="impact-header">
                    <div>
                      <h3 style={{ fontSize: '1rem', color: 'var(--text-primary)' }}>
                        Impact Report for <code style={{ color: 'var(--accent-cyan)' }}>{impactReport.target}</code>
                      </h3>
                      <p style={{ fontSize: '0.825rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
                        {impactReport.summary}
                      </p>
                    </div>
                    <span className={`severity-meter severity-${impactReport.impact_level}`}>
                      {impactReport.impact_level} impact
                    </span>
                  </div>

                  <div className="impact-cols">
                    <div className="impact-col-box">
                      <div className="impact-col-title">
                        Direct Dependents ({impactReport.direct_dependents.length})
                      </div>
                      <div className="impact-tags-list">
                        {impactReport.direct_dependents.length === 0 ? (
                          <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                            No direct dependents.
                          </span>
                        ) : (
                          impactReport.direct_dependents.map((item, i) => (
                            <span key={i} className="impact-tag">
                              {item}
                            </span>
                          ))
                        )}
                      </div>
                    </div>

                    <div className="impact-col-box">
                      <div className="impact-col-title">
                        Transitive Dependents ({impactReport.indirect_dependents.length})
                      </div>
                      <div className="impact-tags-list">
                        {impactReport.indirect_dependents.length === 0 ? (
                          <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                            No indirect dependents.
                          </span>
                        ) : (
                          impactReport.indirect_dependents.map((item, i) => (
                            <span key={i} className="impact-tag">
                              {item}
                            </span>
                          ))
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 5: AI Codebase Intelligence & Q&A */}
          {activeTab === 'qa' && (
            <div className="qa-container">
              <div className="import-form">
                <div className="input-wrapper">
                  <input
                    type="text"
                    className="text-input"
                    placeholder="Ask anything about this codebase (e.g. 'Where is authentication implemented?')..."
                    value={questionInput}
                    onChange={(e) => setQuestionInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleAskQuestion()}
                  />
                </div>
                <button
                  className="btn btn-primary"
                  onClick={() => handleAskQuestion()}
                  disabled={isAsking || !questionInput.trim()}
                >
                  {isAsking ? 'Reasoning...' : 'Ask AI'}
                </button>
              </div>

              {/* Sample Prompts */}
              <div className="qa-presets-row">
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Try asking:</span>
                {[
                  'What does the scanner service do?',
                  'Where is URL parsing handled?',
                  'How does repository ingestion work?',
                  'Explain the database models',
                ].map((prompt, i) => (
                  <button
                    key={i}
                    className="preset-chip"
                    onClick={() => {
                      setQuestionInput(prompt)
                      handleAskQuestion(prompt)
                    }}
                  >
                    {prompt}
                  </button>
                ))}
              </div>

              {qaResponse && (
                <div className="qa-response-box">
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
                    <span style={{ fontSize: '0.8rem', color: 'var(--accent-cyan)', fontWeight: 600 }}>
                      AI Codebase Synthesis
                    </span>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      Confidence: {(qaResponse.confidence * 100).toFixed(0)}%
                    </span>
                  </div>

                  <div className="qa-answer-text">{qaResponse.answer}</div>

                  {qaResponse.citations.length > 0 && (
                    <div>
                      <div className="qa-citations-header">Retrieved Code Citations</div>
                      {qaResponse.citations.map((c, idx) => (
                        <div key={idx} className="citation-card">
                          <div className="citation-top">
                            <span>
                              {c.file_path} (Lines {c.start_line}–{c.end_line})
                            </span>
                            {c.symbol_name && (
                              <span style={{ color: 'var(--text-muted)' }}>Symbol: {c.symbol_name}</span>
                            )}
                          </div>
                          <pre className="citation-snippet">{c.snippet}</pre>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </section>
      )}

      {/* Footer */}
      <footer className="footer">
        {lastChecked && <span>System verified: {lastChecked}</span>}
      </footer>
    </main>
  )
}

export default App
