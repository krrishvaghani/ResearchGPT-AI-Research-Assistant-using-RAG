import { useState, useEffect } from 'react'
import Header from './components/Header'
import PDFUpload from './components/PDFUpload'
import ChatWindow from './components/ChatWindow'
import ResearchSearch from './components/ResearchSearch'
import AuthPage from './components/AuthPage'
import { getDocuments, getToken, getStoredUsername, clearToken } from './api/api'

function App() {
  // Auth state
  const [isAuthenticated, setIsAuthenticated] = useState(() => !!getToken())
  const [username, setUsername] = useState(() => getStoredUsername() || '')

  // Top-level view: 'chat' or 'research'
  const [view, setView] = useState('chat')

  // List of all uploaded docs; the "active" one filters chat (null = search all)
  const [docs, setDocs] = useState([])
  const [activeDocId, setActiveDocId] = useState(null)

  // Load existing docs when authenticated
  useEffect(() => {
    if (!isAuthenticated) return
    getDocuments()
      .then((data) => setDocs(data.documents || []))
      .catch(() => {})
  }, [isAuthenticated])

  // Listen for forced logout (triggered by 401 interceptor)
  useEffect(() => {
    const handle = () => { setIsAuthenticated(false); setUsername(''); setDocs([]) }
    window.addEventListener('auth:logout', handle)
    return () => window.removeEventListener('auth:logout', handle)
  }, [])

  const handleAuth = (name) => {
    setIsAuthenticated(true)
    setUsername(name)
  }

  const handleLogout = () => {
    clearToken()
    setIsAuthenticated(false)
    setUsername('')
    setDocs([])
    setActiveDocId(null)
  }

  const handleDocumentReady = (newDoc) => {
    setDocs((prev) => {
      // Avoid duplicates if somehow the same doc_id is returned twice
      const exists = prev.some((d) => d.document_id === newDoc.document_id)
      return exists ? prev : [...prev, newDoc]
    })
    setActiveDocId(null) // switch to "search all" after every upload
  }

  const activeDoc = docs.find((d) => d.document_id === activeDocId) ?? null

  if (!isAuthenticated) {
    return <AuthPage onAuth={handleAuth} />
  }

  // Tab definitions
  const tabs = [
    {
      id: 'chat',
      label: 'PDF Chat',
      icon: (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
            d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
          />
        </svg>
      ),
    },
    {
      id: 'research',
      label: 'Research Search',
      icon: (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
          />
        </svg>
      ),
    },
  ]

  return (
    <div className="h-screen bg-gray-950 flex flex-col overflow-hidden">
      <Header username={username} onLogout={handleLogout} />

      {/* Tab bar */}
      <nav className="shrink-0 bg-gray-900 border-b border-gray-800 px-4 flex items-center gap-1">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setView(tab.id)}
            className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
              view === tab.id
                ? 'border-indigo-500 text-white'
                : 'border-transparent text-gray-500 hover:text-gray-300'
            }`}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </nav>

      <main className="flex-1 flex overflow-hidden">
        {view === 'chat' ? (
          <>
            {/* Left panel — PDF upload + document list */}
            <aside className="w-80 shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col overflow-y-auto">
              <PDFUpload
                docs={docs}
                activeDocId={activeDocId}
                onDocumentReady={handleDocumentReady}
                onSelectDoc={setActiveDocId}
              />
            </aside>

            {/* Right panel — Chat interface */}
            <div className="flex-1 flex flex-col overflow-hidden">
              <ChatWindow
                doc={activeDoc}
                allDocsCount={docs.length}
                activeDocId={activeDocId}
              />
            </div>
          </>
        ) : (
          <ResearchSearch />
        )}
      </main>
    </div>
  )
}

export default App
