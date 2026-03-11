import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { uploadPDF } from '../api/api'

function PDFUpload({ docs, activeDocId, onDocumentReady, onSelectDoc }) {
  const [uploadState, setUploadState] = useState('idle') // idle | uploading | processing | error
  const [progress, setProgress] = useState(0)
  const [selectedFile, setSelectedFile] = useState(null)
  const [errorMsg, setErrorMsg] = useState('')

  const handleUpload = useCallback(async (file) => {
    setSelectedFile(file)
    setErrorMsg('')
    setUploadState('uploading')
    setProgress(0)

    try {
      const result = await uploadPDF(file, (pct) => {
        setProgress(pct)
        if (pct >= 100) setUploadState('processing')
      })
      onDocumentReady(result)
      setUploadState('idle')
      setSelectedFile(null)
    } catch (err) {
      const detail = err.response?.data?.detail || 'Upload failed. Please try again.'
      setErrorMsg(detail)
      setUploadState('error')
    }
  }, [onDocumentReady])

  const onDrop = useCallback(
    (accepted) => { if (accepted.length > 0) handleUpload(accepted[0]) },
    [handleUpload]
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    maxFiles: 1,
    disabled: uploadState === 'uploading' || uploadState === 'processing',
  })

  const isBusy = uploadState === 'uploading' || uploadState === 'processing'

  return (
    <div className="flex flex-col h-full px-4 py-5 overflow-y-auto">
      {/* Heading */}
      <div className="mb-4">
        <h2 className="text-sm font-bold text-white mb-0.5">Documents</h2>
        <p className="text-xs text-gray-500">Upload PDFs and chat across all of them</p>
      </div>

      {/* Uploaded documents list */}
      {docs.length > 0 && (
        <div className="mb-4 space-y-1.5">
          {/* "All documents" option */}
          <button
            onClick={() => onSelectDoc(null)}
            className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-left transition-colors text-xs ${
              activeDocId === null
                ? 'bg-indigo-600/20 border border-indigo-600/40 text-indigo-300'
                : 'bg-gray-800/50 border border-gray-700/50 text-gray-400 hover:bg-gray-800 hover:text-white'
            }`}
          >
            <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
              />
            </svg>
            <span className="font-medium truncate">All documents ({docs.length})</span>
          </button>

          {/* Individual documents */}
          {docs.map((doc) => (
            <button
              key={doc.document_id}
              onClick={() => onSelectDoc(doc.document_id)}
              className={`w-full flex items-start gap-2.5 px-3 py-2 rounded-xl text-left transition-colors ${
                activeDocId === doc.document_id
                  ? 'bg-indigo-600/20 border border-indigo-600/40'
                  : 'bg-gray-800/50 border border-gray-700/50 hover:bg-gray-800'
              }`}
            >
              <div className="w-6 h-6 rounded-lg bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center shrink-0 mt-0.5">
                <svg className="w-3 h-3 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
              </div>
              <div className="min-w-0">
                <p className={`text-xs font-medium truncate ${activeDocId === doc.document_id ? 'text-indigo-300' : 'text-gray-300'}`}>
                  {doc.filename}
                </p>
                <p className="text-xs text-gray-600 mt-0.5">
                  {doc.pages} pages &middot; {doc.chunks} chunks
                </p>
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Divider */}
      {docs.length > 0 && (
        <p className="text-xs uppercase tracking-widest text-gray-600 mb-3">Add another PDF</p>
      )}

      {/* Drop Zone */}
      <div
        {...getRootProps()}
        className={`rounded-2xl border-2 border-dashed p-5 text-center transition-all duration-200 select-none ${
          isBusy
            ? 'border-gray-700 bg-gray-900/60 cursor-not-allowed'
            : isDragActive
            ? 'border-indigo-400 bg-indigo-500/10 cursor-copy'
            : 'border-gray-700 bg-gray-900/60 hover:border-indigo-500 hover:bg-gray-800/60 cursor-pointer'
        }`}
      >
        <input {...getInputProps()} />

        {!isBusy ? (
          <>
            <div className="w-10 h-10 mx-auto mb-2 rounded-xl bg-gray-800 flex items-center justify-center">
              {uploadState === 'error' ? (
                <svg className="w-5 h-5 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
                  />
                </svg>
              ) : (
                <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                  />
                </svg>
              )}
            </div>
            <p className="text-xs font-semibold text-white mb-1">
              {isDragActive ? 'Drop your PDF here' : docs.length === 0 ? 'Drag & drop a PDF' : 'Drop another PDF'}
            </p>
            <p className="text-xs text-gray-500">or click to browse &middot; max 50 MB</p>
          </>
        ) : (
          <>
            <div className="w-10 h-10 mx-auto mb-2 rounded-xl bg-indigo-500/10 border border-indigo-500/30 flex items-center justify-center">
              <svg className="w-5 h-5 text-indigo-400 animate-pulse" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
            </div>
            <p className="text-white text-xs font-medium truncate px-3 mb-1">{selectedFile?.name}</p>
            <p className="text-gray-400 text-xs mb-2">
              {uploadState === 'uploading' ? `Uploadingâ€¦ ${progress}%` : 'Building vector indexâ€¦'}
            </p>
            <div className="w-full bg-gray-800 rounded-full h-1 overflow-hidden">
              <div
                className={`h-1 rounded-full transition-all duration-300 ${
                  uploadState === 'processing'
                    ? 'w-full bg-gradient-to-r from-indigo-500 to-purple-500 animate-pulse'
                    : 'bg-gradient-to-r from-indigo-500 to-purple-500'
                }`}
                style={{ width: uploadState === 'processing' ? '100%' : `${progress}%` }}
              />
            </div>
          </>
        )}
      </div>

      {/* Error banner */}
      {errorMsg && (
        <div className="mt-3 flex items-start gap-2 p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-xs">
          <svg className="w-3.5 h-3.5 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <span><span className="font-medium">Error:</span> {errorMsg}</span>
        </div>
      )}
    </div>
  )
}

export default PDFUpload
