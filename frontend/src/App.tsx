import { useEffect, useState } from 'react'

interface HealthResponse {
  status: string
}

type ConnectionStatus = 'connecting' | 'connected' | 'error'

export function App() {
  const [status, setStatus] = useState<ConnectionStatus>('connecting')
  const [healthData, setHealthData] = useState<HealthResponse | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [lastChecked, setLastChecked] = useState<string | null>(null)

  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

  const checkHealth = async () => {
    setStatus('connecting')
    setErrorMessage(null)
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
    } catch (err: unknown) {
      setStatus('error')
      setErrorMessage(err instanceof Error ? err.message : 'Unknown connection error')
    } finally {
      setLastChecked(new Date().toLocaleTimeString())
    }
  }

  useEffect(() => {
    checkHealth()
  }, [])

  return (
    <main className="card" id="main-card">
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
        </div>
      </header>

      <p className="subtitle">
        Intelligent codebase intelligence platform skeleton.
      </p>

      <section className={`status-box status-${status}`} id="connection-status-container">
        <div className="status-info">
          <div className="pulse-indicator" aria-hidden="true">
            <div className="pulse-dot" />
            <div className="pulse-ring" />
          </div>
          <div className="status-text" id="status-display">
            {status === 'connected' && 'Backend Connected'}
            {status === 'connecting' && 'Connecting to Backend...'}
            {status === 'error' && 'Connection Failed'}
          </div>
        </div>
        <div className="endpoint-badge" id="endpoint-badge">
          GET /health
        </div>
      </section>

      <div className="details-grid">
        <div className="detail-item">
          <div className="detail-label">API Endpoint</div>
          <div className="detail-value" id="api-url-display">{apiBaseUrl}/health</div>
        </div>
        <div className="detail-item">
          <div className="detail-label">Response Payload</div>
          <div className="detail-value" id="response-payload-display">
            {healthData ? JSON.stringify(healthData) : errorMessage || 'Pending...'}
          </div>
        </div>
      </div>

      <div className="actions">
        <button
          id="btn-recheck"
          className="btn btn-primary"
          onClick={checkHealth}
          disabled={status === 'connecting'}
        >
          {status === 'connecting' ? 'Checking...' : 'Re-check Status'}
        </button>
      </div>

      <footer className="footer">
        {lastChecked && <span>Last verified: {lastChecked}</span>}
      </footer>
    </main>
  )
}
export default App
