import axios from 'axios'

const api = axios.create({
  baseURL: 'http://localhost:8000/api',
})

// ── Token helpers ──────────────────────────────────────────────────────────

export function getToken() {
  return localStorage.getItem('jwt_token')
}

export function setToken(token, username) {
  localStorage.setItem('jwt_token', token)
  if (username) localStorage.setItem('username', username)
}

export function clearToken() {
  localStorage.removeItem('jwt_token')
  localStorage.removeItem('username')
}

export function getStoredUsername() {
  return localStorage.getItem('username')
}

// Attach Bearer token to every outgoing request automatically.
api.interceptors.request.use((config) => {
  const token = getToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// On 401, clear stored credentials and notify the app.
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      clearToken()
      window.dispatchEvent(new Event('auth:logout'))
    }
    return Promise.reject(err)
  }
)

// ── Auth ───────────────────────────────────────────────────────────────────

export async function register(username, email, password) {
  const response = await api.post('/register', { username, email, password })
  return response.data
}

export async function login(username, password) {
  const response = await api.post('/login', { username, password })
  return response.data
}

/**
 * Upload a PDF file to the backend for processing.
 * @param {File} file
 * @param {(progress: number) => void} [onProgress]
 */
export async function uploadPDF(file, onProgress) {
  const formData = new FormData()
  formData.append('file', file)

  const response = await api.post('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (event) => {
      if (onProgress && event.total) {
        onProgress(Math.round((event.loaded * 100) / event.total))
      }
    },
  })
  return response.data
}

/**
 * Fetch the list of all uploaded documents from the backend.
 * @returns {{ documents: Array, total: number }}
 */
export async function getDocuments() {
  const response = await api.get('/documents')
  return response.data
}

/**
 * Send a question about an uploaded document.
 * @param {string} documentId
 * @param {string} question
 */
export async function sendMessage(documentId, question) {
  const response = await api.post('/chat', {
    document_id: documentId,
    question,
  })
  return response.data
}

/**
 * Ask a question via the RAG pipeline (POST /ask).
 * @param {string} question
 * @param {string|null} [documentId] - optional, restricts search to one doc
 */
export async function askQuestion(question, documentId = null) {
  const payload = { question }
  if (documentId) payload.document_id = documentId
  const response = await api.post('/ask', payload)
  return response.data
}

/**
 * Search arXiv for research papers.
 * @param {string} query - keyword(s) to search
 * @param {number} [maxResults=10] - number of results
 */
export async function searchPapers(query, maxResults = 10) {
  const response = await api.get('/search_papers', {
    params: { query, max_results: maxResults },
  })
  return response.data
}

/**
 * Generate an AI summary for the provided text.
 * @param {string} text - research paper text or abstract
 */
export async function summarizePaper(text) {
  const response = await api.post('/summarize', { text })
  return response.data
}
