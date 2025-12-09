import { useState, useEffect, useRef } from 'react'
import { useDropzone } from 'react-dropzone'
import { Navigate } from 'react-router-dom'
import { Upload as UploadIcon, FileText, AlertCircle, CheckCircle } from 'lucide-react'
import { useUpload } from '../hooks/useJobProgress'
import { formatFileSize } from '../utils/formats'
import { FILE_LIMITS } from '../utils/constants'

export default function Upload() {
  const [selectedFiles, setSelectedFiles] = useState([])
  // Output formats - can be extended via config
  const selectedFormats = ['msf']
  const [uploadResults, setUploadResults] = useState([])
  const [currentUploadIndex, setCurrentUploadIndex] = useState(0)
  const [shouldNavigate, setShouldNavigate] = useState(false)
  const { uploadFile, uploadProgress, isUploading, uploadError } = useUpload()
  const fileInputRef = useRef(null)

  const onDrop = (acceptedFiles, rejectedFiles) => {
    if (rejectedFiles.length > 0) {
      const rejection = rejectedFiles[0]
      console.error('File rejected:', rejection.errors)
      return
    }

    if (acceptedFiles.length > 0) {
      setSelectedFiles(prevFiles => {
        const existingNames = new Set(prevFiles.map(f => f.name + f.size))
        const newFiles = acceptedFiles.filter(file => !existingNames.has(file.name + file.size))
        return [...prevFiles, ...newFiles]
      })
      setUploadResults([])
    }
  }

  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    maxSize: FILE_LIMITS.MAX_SIZE_BYTES,
    multiple: true,
    disabled: isUploading
  })

  const handleUpload = async () => {
    if (selectedFiles.length === 0) return

    const results = []
    for (let i = 0; i < selectedFiles.length; i++) {
      setCurrentUploadIndex(i)
      try {
        const result = await uploadFile(selectedFiles[i], {
          outputFormats: selectedFormats
        })
        results.push({ ...result, filename: selectedFiles[i].name })
      } catch (error) {
        console.error(`Upload failed for ${selectedFiles[i].name}:`, error)
        results.push({ error: error.message, filename: selectedFiles[i].name })
      }
    }
    setUploadResults(results)
    setSelectedFiles([])
    setCurrentUploadIndex(0)
  }

  const handleFileInputChange = (event) => {
    const files = Array.from(event.target.files || [])
    if (files.length > 0) {
      setSelectedFiles(prevFiles => {
        const existingNames = new Set(prevFiles.map(f => f.name + f.size))
        const newFiles = files.filter(file => !existingNames.has(file.name + file.size))
        return [...prevFiles, ...newFiles]
      })
      setUploadResults([])
    }
    event.target.value = ''
  }

  const openFileDialog = () => {
    fileInputRef.current?.click()
  }

  const getTotalFileSize = () => {
    return selectedFiles.reduce((total, file) => total + file.size, 0)
  }

  // Navigate to jobs list after all uploads complete
  useEffect(() => {
    if (uploadResults.length > 0 && !isUploading) {
      const timer = setTimeout(() => {
        setShouldNavigate(true)
      }, 1000)
      return () => clearTimeout(timer)
    }
  }, [uploadResults, isUploading])

  if (shouldNavigate && uploadResults.length > 0) {
    return <Navigate to="/jobs" replace />
  }

  return (
    <div className="max-w-2xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-slate-900">Upload PDF</h1>
        <p className="mt-1 text-sm text-slate-600">
          Upload PDF files for document processing
        </p>
      </div>

      {/* Upload Area */}
      <div className="bg-white rounded-xl p-6 shadow-sm">
        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf"
          onChange={handleFileInputChange}
          style={{ display: 'none' }}
        />
        <div
          {...getRootProps()}
          className={`
            border-2 border-dashed rounded-lg p-8 text-center transition-colors
            ${isDragActive && !isDragReject
              ? 'border-blue-400 bg-blue-50 cursor-pointer'
              : isDragReject
              ? 'border-red-400 bg-red-50 cursor-pointer'
              : 'border-gray-300 hover:border-gray-400 cursor-pointer'
            }
            ${isUploading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
          `}
        >
          <input {...getInputProps()} />

          <div className="flex flex-col items-center">
            <UploadIcon className={`h-12 w-12 mb-4 ${
              isDragActive && !isDragReject ? 'text-blue-500' :
              isDragReject ? 'text-red-500' : 'text-slate-400'
            }`} />

            {isDragActive && !isDragReject ? (
              <p className="text-lg font-medium text-blue-700">Drop the PDF here</p>
            ) : isDragReject ? (
              <p className="text-lg font-medium text-red-700">Invalid file type</p>
            ) : (
              <>
                <p className="text-lg font-medium text-slate-700 mb-2">
                  Drop PDF files here, or click to browse
                </p>
                <p className="text-sm text-slate-500">
                  Multiple files supported • Max size per file: {formatFileSize(FILE_LIMITS.MAX_SIZE_BYTES)}
                </p>
              </>
            )}
          </div>
        </div>

        {/* Selected Files */}
        {selectedFiles.length > 0 && !isUploading && (
          <div className="mt-4 p-4 bg-gray-50 rounded-lg">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-medium text-slate-700">
                  Selected Files ({selectedFiles.length})
                </h3>
                <p className="text-xs text-slate-500 mt-1">
                  Total size: {formatFileSize(getTotalFileSize())}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={openFileDialog}
                  className="px-3 py-1.5 text-sm bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors cursor-pointer"
                >
                  Add More Files
                </button>
                <button
                  onClick={() => setSelectedFiles([])}
                  className="px-3 py-1.5 text-sm bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors cursor-pointer"
                >
                  Clear All
                </button>
                <button
                  onClick={handleUpload}
                  className="px-3 py-1.5 bg-slate-800 text-white rounded-lg text-sm font-medium hover:bg-slate-700 transition-colors cursor-pointer"
                >
                  Upload All
                </button>
              </div>
            </div>
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {selectedFiles.map((file, index) => (
                <div key={index} className="flex items-center justify-between p-2 bg-white rounded">
                  <div className="flex items-center">
                    <FileText className="h-4 w-4 text-slate-500 mr-2" />
                    <div>
                      <p className="text-xs font-medium text-slate-700">
                        {file.name}
                      </p>
                      <p className="text-xs text-slate-500">
                        {formatFileSize(file.size)}
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => setSelectedFiles(files => files.filter((_, i) => i !== index))}
                    className="text-xs text-red-600 hover:text-red-700 cursor-pointer"
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Upload Progress */}
        {isUploading && (
          <div className="mt-4 p-4 bg-blue-50 rounded-lg">
            <div className="flex items-center mb-2">
              <UploadIcon className="h-5 w-5 text-blue-600 mr-3 animate-pulse" />
              <span className="text-sm font-medium text-blue-700">
                Uploading file {currentUploadIndex + 1} of {selectedFiles.length}... {uploadProgress}%
              </span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
          </div>
        )}

        {/* Upload Error */}
        {uploadError && (
          <div className="mt-4 p-4 bg-red-50 rounded-xl">
            <div className="flex items-center">
              <AlertCircle className="h-5 w-5 text-red-500 mr-3" />
              <div>
                <p className="text-sm font-medium text-red-700">Upload Failed</p>
                <p className="text-sm text-red-600">
                  {uploadError.response?.data?.detail || uploadError.message}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Upload Success */}
        {uploadResults.length > 0 && !isUploading && (
          <div className="mt-4 p-4 bg-green-50 rounded-xl">
            <div className="flex items-center mb-2">
              <CheckCircle className="h-5 w-5 text-green-500 mr-3" />
              <div>
                <p className="text-sm font-medium text-green-700">
                  Upload Complete
                </p>
                <p className="text-sm text-green-600">
                  Successfully uploaded {uploadResults.filter(r => !r.error).length} of {uploadResults.length} files
                </p>
              </div>
            </div>
            {uploadResults.some(r => r.error) && (
              <div className="mt-2 text-xs text-red-600">
                Failed uploads:
                {uploadResults.filter(r => r.error).map((r, i) => (
                  <div key={i}>• {r.filename}: {r.error}</div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Upload Guidelines */}
      <div className="mt-6 bg-gray-50 rounded-xl p-4">
        <h3 className="text-sm font-medium text-gray-700 mb-2">File Requirements</h3>
        <ul className="text-xs text-gray-600 space-y-1">
          <li>• PDF files only</li>
          <li>• Maximum size: {formatFileSize(FILE_LIMITS.MAX_SIZE_BYTES)}</li>
          <li>• Files should contain instrument specification tables</li>
          <li>• Text-based PDFs work best (not scanned images)</li>
        </ul>
      </div>
    </div>
  )
}