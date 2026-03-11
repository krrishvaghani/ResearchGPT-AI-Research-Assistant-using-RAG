import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { searchPapers, summarizePaper } from '../api/api'

// ── Sub-components ────────────────────────────────────────────────────────────

function Spinner() {
  return (
    <div className="flex gap-1 items-center">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce"
          style={{ animationDelay: `${i * 0.15}s` }}
        />
      ))}
    </div>
  )
}

function PaperCard({ paper }) {
  const [expanded, setExpanded] = useState(false)
  const [summaryState, setSummaryState] = useState('idle') // idle | loading | done | error
  const [summary, setSummary] = useState('')
  const [summaryError, setSummaryError] = useState('')

  const handleSummarize = async () => {
    setSummaryState('loading')
    setSummaryError('')
    try {
      const data = await summarizePaper(paper.summary)
      setSummary(data.summary)
      setSummaryState('done')
    } catch (err) {
      const detail = err.response?.data?.detail || 'Summarization failed. Please try again.'
      setSummaryError(detail)
      setSummaryState('error')
    }
  }

  return (
    <div className="rounded-2xl bg-gray-900 border border-gray-800 overflow-hidden">
      {/* Header row */}
      <div className="p-4">
        <div className="flex items-start justify-between gap-3 mb-2">
          <h3 className="text-sm font-semibold text-white leading-snug flex-1">{paper.title}</h3>
          {paper.pdf_url && (
            <a
              href={paper.pdf_url}
              target="_blank"
              rel="noopener noreferrer"
              className="shrink-0 flex items-center gap-1 px-2.5 py-1 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 hover:bg-red-500/20 text-xs font-medium transition-colors"
            >
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
              PDF
            </a>
          )}
        </div>

        {/* Authors */}
        {paper.authors.length > 0 && (
          <p className="text-xs text-indigo-400 mb-2 truncate">
            {paper.authors.slice(0, 4).join(', ')}
            {paper.authors.length > 4 && ` +${paper.authors.length - 4} more`}
          </p>
        )}

        {/* Abstract toggle */}
        <button
          onClick={() => setExpanded((v) => !v)}
          className="text-xs text-gray-500 hover:text-gray-300 transition-colors flex items-center gap-1"
        >
          <svg
            className={`w-3 h-3 transition-transform duration-200 ${expanded ? 'rotate-90' : ''}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          {expanded ? 'Hide' : 'View'} abstract
        </button>

        {expanded && (
          <p className="mt-2 text-xs text-gray-400 leading-relaxed border-t border-gray-800 pt-3">
            {paper.summary}
          </p>
        )}
      </div>

      {/* Action bar */}
      <div className="px-4 pb-4 flex items-center justify-between gap-3">
        <button
          onClick={handleSummarize}
          disabled={summaryState === 'loading' || summaryState === 'done'}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-indigo-600/20 border border-indigo-600/40 text-indigo-300 hover:bg-indigo-600/30 disabled:opacity-50 disabled:cursor-not-allowed text-xs font-medium transition-colors"
        >
          {summaryState === 'loading' ? (
            <>
              <Spinner />
              Summarizing…
            </>
          ) : summaryState === 'done' ? (
            <>
              <svg className="w-3.5 h-3.5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              Summarized
            </>
          ) : (
            <>
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                  d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
                />
              </svg>
              AI Summary
            </>
          )}
        </button>

        {summaryState === 'done' && (
          <button
            onClick={() => { setSummaryState('idle'); setSummary('') }}
            className="text-xs text-gray-600 hover:text-gray-400 transition-colors"
          >
            Clear
          </button>
        )}
      </div>

      {/* AI Summary panel */}
      {summaryState === 'done' && summary && (
        <div className="mx-4 mb-4 p-3 rounded-xl bg-gray-800/60 border border-gray-700">
          <p className="text-xs uppercase tracking-widest text-gray-600 mb-2">AI Summary</p>
          <div className="prose prose-sm prose-invert max-w-none text-xs leading-relaxed">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{summary}</ReactMarkdown>
          </div>
        </div>
      )}

      {/* Error banner */}
      {summaryState === 'error' && summaryError && (
        <div className="mx-4 mb-4 flex items-start gap-2 p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-xs">
          <svg className="w-3.5 h-3.5 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <span>{summaryError}</span>
        </div>
      )}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

function ResearchSearch() {
  const [query, setQuery] = useState('')
  const [searchState, setSearchState] = useState('idle') // idle | loading | done | error
  const [papers, setPapers] = useState([])
  const [searchError, setSearchError] = useState('')

  const handleSearch = async (e) => {
    e.preventDefault()
    const q = query.trim()
    if (!q) return

    setSearchState('loading')
    setSearchError('')
    setPapers([])

    try {
      const data = await searchPapers(q)
      setPapers(data.papers || [])
      setSearchState('done')
    } catch (err) {
      const detail = err.response?.data?.detail || 'Search failed. Please try again.'
      setSearchError(detail)
      setSearchState('loading' === 'loading' ? 'error' : 'error')
      setSearchState('error')
    }
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-gray-950">
      {/* Search bar */}
      <div className="shrink-0 border-b border-gray-800 bg-gray-900 px-6 py-4">
        <form onSubmit={handleSearch} className="flex gap-3 items-center max-w-3xl">
          <div className="flex-1 relative">
            <svg
              className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500 pointer-events-none"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder='Search arXiv — e.g. "transformer attention mechanism"'
              className="w-full bg-gray-800 text-white placeholder-gray-500 rounded-xl pl-9 pr-4 py-2.5 text-sm outline-none border border-gray-700 focus:border-indigo-500 transition-colors"
              disabled={searchState === 'loading'}
            />
          </div>
          <button
            type="submit"
            disabled={!query.trim() || searchState === 'loading'}
            className="shrink-0 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-700 disabled:cursor-not-allowed text-white text-sm font-medium transition-colors"
          >
            {searchState === 'loading' ? 'Searching…' : 'Search'}
          </button>
        </form>
        <p className="text-xs text-gray-600 mt-1.5 max-w-3xl">
          Powered by the arXiv API &middot; Results include title, authors, abstract, and PDF link
        </p>
      </div>

      {/* Results area */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        {/* Idle state */}
        {searchState === 'idle' && (
          <div className="flex flex-col items-center justify-center h-full gap-4 text-center">
            <div className="w-16 h-16 rounded-2xl bg-gray-800/80 border border-gray-700 flex items-center justify-center">
              <svg className="w-8 h-8 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                  d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
                />
              </svg>
            </div>
            <div>
              <p className="text-base font-semibold text-gray-400">Search for research papers</p>
              <p className="text-sm text-gray-600 mt-1">
                Enter keywords above to find papers from arXiv
              </p>
            </div>
            <div className="flex flex-wrap justify-center gap-2 mt-2">
              {['deep learning', 'large language models', 'computer vision', 'reinforcement learning'].map((tag) => (
                <button
                  key={tag}
                  onClick={() => { setQuery(tag) }}
                  className="px-3 py-1.5 rounded-full bg-gray-800 border border-gray-700 text-gray-400 hover:text-white hover:border-gray-600 text-xs transition-colors"
                >
                  {tag}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Loading */}
        {searchState === 'loading' && (
          <div className="flex flex-col items-center justify-center h-full gap-3">
            <div className="flex gap-1.5">
              {[0, 1, 2, 3].map((i) => (
                <span
                  key={i}
                  className="w-2 h-2 rounded-full bg-indigo-500 animate-bounce"
                  style={{ animationDelay: `${i * 0.12}s` }}
                />
              ))}
            </div>
            <p className="text-sm text-gray-500">Searching arXiv for "{query}"…</p>
          </div>
        )}

        {/* Error */}
        {searchState === 'error' && (
          <div className="flex flex-col items-center justify-center h-full gap-3">
            <div className="p-4 rounded-2xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm flex items-start gap-3 max-w-md">
              <svg className="w-5 h-5 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <span>{searchError}</span>
            </div>
            <button
              onClick={() => setSearchState('idle')}
              className="text-xs text-gray-600 hover:text-gray-400 transition-colors"
            >
              Try again
            </button>
          </div>
        )}

        {/* Results */}
        {searchState === 'done' && (
          <>
            <div className="flex items-center justify-between mb-4 max-w-4xl">
              <p className="text-sm text-gray-400">
                {papers.length === 0
                  ? 'No papers found.'
                  : `${papers.length} paper${papers.length > 1 ? 's' : ''} found for "${query}"`}
              </p>
              <button
                onClick={() => { setSearchState('idle'); setPapers([]); setQuery('') }}
                className="text-xs text-gray-600 hover:text-gray-400 transition-colors"
              >
                Clear results
              </button>
            </div>

            {papers.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 gap-3 text-center">
                <p className="text-gray-500 text-sm">No results found for "{query}".</p>
                <p className="text-gray-600 text-xs">Try different or broader keywords.</p>
              </div>
            ) : (
              <div className="space-y-4 max-w-4xl">
                {papers.map((paper, i) => (
                  <PaperCard key={i} paper={paper} />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

export default ResearchSearch
