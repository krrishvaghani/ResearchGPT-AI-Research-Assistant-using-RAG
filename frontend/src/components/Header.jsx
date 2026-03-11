function Header({ username, onLogout }) {
  return (
    <header className="bg-gray-900 border-b border-gray-800 shrink-0">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4 flex items-center gap-3">
        {/* Logo */}
        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shrink-0">
          <svg
            className="w-5 h-5 text-white"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
            />
          </svg>
        </div>
        {/* Title */}
        <div>
          <h1 className="text-base font-bold text-white leading-tight">
            AI Research PDF Chat Assistant
          </h1>
          <p className="text-xs text-gray-400 leading-tight">
            PDF Chat Platform &middot; Powered by RAG
          </p>
        </div>

        <div className="ml-auto flex items-center gap-3">
          {/* RAG badge */}
          <div className="hidden sm:flex items-center gap-1.5 px-3 py-1 rounded-full bg-indigo-600/20 border border-indigo-600/30">
            <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse" />
            <span className="text-xs text-indigo-300 font-medium">RAG Enabled</span>
          </div>

          {/* User + logout */}
          {username && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-400 hidden sm:block">
                <span className="text-gray-600">@</span>{username}
              </span>
              <button
                onClick={onLogout}
                title="Sign out"
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-800 border border-gray-700 text-gray-400 hover:text-white hover:bg-gray-700 text-xs transition-colors"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
                  />
                </svg>
                Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}

export default Header
