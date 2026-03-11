import { useState, useRef, useEffect } from 'react'
import ChatMessage from './ChatMessage'
import { askQuestion } from '../api/api'

function TypingIndicator() {
  return (
    <div className="flex gap-3">
      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-600 to-indigo-600 shrink-0 flex items-center justify-center text-xs font-bold text-white">
        AI
      </div>
      <div className="px-4 py-3 rounded-2xl rounded-tl-sm bg-gray-800 flex items-center">
        <div className="flex gap-1">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="w-2 h-2 rounded-full bg-gray-500 animate-bounce"
              style={{ animationDelay: `${i * 0.15}s` }}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

function now() {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function ChatWindow({ doc, allDocsCount = 0 }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

  // Reset chat history when the document or doc set changes
  useEffect(() => {
    if (doc) {
      setMessages([
        {
          id: 'welcome',
          role: 'assistant',
          content: `I've analyzed **"${doc.filename}"** — ${doc.pages} pages split into ${doc.chunks} searchable chunks.\n\nAsk me anything about this document!`,
          sources: [],
          timestamp: now(),
        },
      ])
    } else if (allDocsCount > 0) {
      setMessages([
        {
          id: 'welcome',
          role: 'assistant',
          content: `I have access to **${allDocsCount} document${allDocsCount > 1 ? 's' : ''}**. Ask me anything and I'll search across all of them!\n\nSelect a specific document on the left to narrow your search.`,
          sources: [],
          timestamp: now(),
        },
      ])
    } else {
      setMessages([])
    }
  }, [doc?.document_id, allDocsCount])

  // Auto-scroll on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  const handleSubmit = async (e) => {
    e.preventDefault()
    const question = input.trim()
    if (!question || isLoading) return

    const userMsg = {
      id: `u-${Date.now()}`,
      role: 'user',
      content: question,
      sources: [],
      timestamp: now(),
    }

    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setIsLoading(true)

    try {
      const data = await askQuestion(question, doc?.document_id ?? null)
      setMessages((prev) => [
        ...prev,
        {
          id: `a-${Date.now()}`,
          role: 'assistant',
          content: data.answer,
          sources: data.sources ?? [],
          timestamp: now(),
        },
      ])
    } catch (err) {
      const detail = err.response?.data?.detail || 'An unexpected error occurred.'
      setMessages((prev) => [
        ...prev,
        {
          id: `e-${Date.now()}`,
          role: 'assistant',
          content: `⚠️ **Error:** ${detail}`,
          sources: [],
          timestamp: now(),
        },
      ])
    } finally {
      setIsLoading(false)
      inputRef.current?.focus()
    }
  }

  // ── No document uploaded yet ──────────────────────────────────────────
  if (!doc && allDocsCount === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-4 bg-gray-950 px-8 text-center">
        <div className="w-16 h-16 rounded-2xl bg-gray-800/80 border border-gray-700 flex items-center justify-center">
          <svg className="w-8 h-8 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
            />
          </svg>
        </div>
        <div>
          <p className="text-base font-semibold text-gray-400">No document loaded</p>
          <p className="text-sm text-gray-600 mt-1">
            Upload a PDF on the left to start chatting
          </p>
        </div>
      </div>
    )
  }

  // ── Chat UI ───────────────────────────────────────────────────────────
  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-gray-950">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
        {messages.map((msg) => (
          <ChatMessage key={msg.id} message={msg} />
        ))}
        {isLoading && <TypingIndicator />}
        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <div className="shrink-0 border-t border-gray-800 bg-gray-900 px-6 py-4">
        <form onSubmit={handleSubmit} className="flex gap-3 items-end">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSubmit(e)
              }
            }}
            placeholder={doc ? `Ask about "${doc.filename}"…` : 'Ask anything across all documents…'}
            rows={1}
            disabled={isLoading}
            className="flex-1 bg-gray-800 text-white placeholder-gray-500 rounded-xl px-4 py-3 text-sm resize-none outline-none border border-gray-700 focus:border-indigo-500 transition-colors leading-relaxed"
            style={{ maxHeight: '120px' }}
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="shrink-0 w-10 h-10 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-700 disabled:cursor-not-allowed text-white flex items-center justify-center transition-colors"
            aria-label="Send"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
              />
            </svg>
          </button>
        </form>
        <p className="text-xs text-gray-700 text-center mt-2">
          Press <kbd className="text-gray-600">Enter</kbd> to send &middot;{' '}
          <kbd className="text-gray-600">Shift+Enter</kbd> for new line
        </p>
      </div>
    </div>
  )
}

export default ChatWindow
