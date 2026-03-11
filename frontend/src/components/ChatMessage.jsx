import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

function ChatMessage({ message }) {
  const [showSources, setShowSources] = useState(false)
  const isUser = message.role === 'user'

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      {/* Avatar */}
      <div
        className={`w-8 h-8 rounded-full shrink-0 flex items-center justify-center text-xs font-bold ${
          isUser
            ? 'bg-indigo-600 text-white'
            : 'bg-gradient-to-br from-purple-600 to-indigo-600 text-white'
        }`}
      >
        {isUser ? 'You' : 'AI'}
      </div>

      {/* Bubble + metadata */}
      <div className={`flex flex-col gap-1 max-w-[75%] ${isUser ? 'items-end' : 'items-start'}`}>
        {/* Message bubble */}
        <div
          className={`px-4 py-3 rounded-2xl text-sm leading-relaxed ${
            isUser
              ? 'bg-indigo-600 text-white rounded-tr-sm'
              : 'bg-gray-800 text-gray-100 rounded-tl-sm'
          }`}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : (
            <div className="prose prose-sm prose-invert max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.content}
              </ReactMarkdown>
            </div>
          )}
        </div>

        {/* Source citations (AI only) */}
        {!isUser && message.sources?.length > 0 && (
          <div className="w-full">
            <button
              onClick={() => setShowSources((v) => !v)}
              className="flex items-center gap-1.5 text-xs text-gray-600 hover:text-gray-400 transition-colors mt-0.5"
            >
              <svg
                className={`w-3 h-3 transition-transform duration-200 ${showSources ? 'rotate-90' : ''}`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
              {showSources ? 'Hide' : 'View'} {message.sources.length} source
              {message.sources.length > 1 ? 's' : ''}
            </button>

            {showSources && (
              <div className="mt-2 space-y-2">
                {message.sources.map((src, i) => (
                  <div
                    key={i}
                    className="p-3 rounded-xl bg-gray-900 border border-gray-700 text-xs text-gray-400 leading-relaxed"
                  >
                    <div className="flex items-center flex-wrap gap-x-1.5 gap-y-0.5 mb-1">
                      <span className="text-indigo-400 font-semibold">Excerpt {src.index + 1}</span>
                      {src.filename && <span className="text-gray-600">·</span>}
                      {src.filename && <span className="text-gray-400 truncate max-w-[160px]" title={src.filename}>{src.filename}</span>}
                      {src.page != null && <span className="text-gray-500 shrink-0">· Page {src.page + 1}</span>}
                    </div>
                    <p className="line-clamp-4">{src.content}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Timestamp */}
        <span className="text-xs text-gray-700 px-1">{message.timestamp}</span>
      </div>
    </div>
  )
}

export default ChatMessage
