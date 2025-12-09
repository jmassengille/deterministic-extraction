import axios from 'axios'
import { toast } from 'sonner'
import { getErrorMessage, isAuthError, isNetworkError, isServerError } from '../utils/errorHandling'

// Create axios instance with default config
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
  timeout: 60000,
})

// Request interceptor for adding auth tokens and request IDs
api.interceptors.request.use(
  (config) => {
    // Add request ID for tracking
    config.headers['X-Request-ID'] = crypto.randomUUID()

    // Add auth token if available (stub for future implementation)
    const token = localStorage.getItem('mox_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }

    // Handle FormData vs JSON content types
    if (config.data instanceof FormData) {
      delete config.headers['Content-Type']
    } else if (config.data && typeof config.data === 'object') {
      config.headers['Content-Type'] = 'application/json'
    }

    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (isAuthError(error)) {
      localStorage.removeItem('mox_token')
      console.warn('Unauthorized request - token may be expired')
      toast.error('Session expired', {
        description: 'Please log in again'
      })
    } else if (isNetworkError(error)) {
      console.error('Network error:', error)
      toast.error('Connection lost', {
        description: 'Unable to reach server. Check your connection.'
      })
    } else if (isServerError(error)) {
      console.error('Server error:', error.response?.data)
      toast.error('Server error', {
        description: 'The server encountered an error. Please try again later.'
      })
    }

    return Promise.reject(error)
  }
)

// Health API
export const healthAPI = {
  check: () => api.get('/api/health'),
}

// Jobs API
export const jobsAPI = {
  list: (params = {}) => api.get('/api/jobs', { params }),
  get: (jobId) => api.get(`/api/jobs/${jobId}`),
  delete: (jobId) => api.delete(`/api/jobs/${jobId}`),

  // Multi-format download support
  download: (jobId, format = 'json', key = null) => {
    const params = { format }
    if (key) params.key = key
    return api.get(`/api/jobs/${jobId}/download`, { params, responseType: 'blob' })
  },

  // Get available download formats for a job
  getFormats: (jobId) => api.get(`/api/jobs/${jobId}/formats`),
}

// Upload API
export const uploadAPI = {
  /**
   * Upload a PDF file for processing.
   * @param {File} file - PDF file to upload
   * @param {Object} options - Upload options
   * @param {string[]} options.outputFormats - Output formats (from registered serializers)
   * @param {Object} options.metadata - Additional metadata
   * @param {Function} options.onProgress - Progress callback
   */
  upload: (file, options = {}) => {
    const formData = new FormData()
    formData.append('file', file)

    // Output formats - use JSON as default if not specified
    const formats = options.outputFormats || ['json']
    formData.append('output_formats', formats.join(','))

    // Optional metadata
    if (options.metadata) {
      formData.append('metadata', JSON.stringify(options.metadata))
    }

    return api.post('/api/upload', formData, {
      onUploadProgress: (progressEvent) => {
        if (options.onProgress) {
          const percentCompleted = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          )
          options.onProgress(percentCompleted)
        }
      },
    })
  },
}

// Editor API
export const editorAPI = {
  getData: (jobId) => api.get(`/api/jobs/${jobId}/editor`),
  saveMSF: (jobId, content) => api.put(`/api/jobs/${jobId}/editor/msf`, { content }),
  getPDF: (jobId) => api.get(`/api/jobs/${jobId}/editor/pdf`, { responseType: 'blob' }),
}

// Progress API (Server-Sent Events)
export const progressAPI = {
  // Create EventSource for job progress
  streamProgress: (jobId, onMessage, onError, onOpen) => {
    const url = `/api/jobs/${jobId}/progress`
    console.log(`[SSE] Creating EventSource for: ${url}`)

    try {
      const eventSource = new EventSource(url)

      let hasOpened = false

      eventSource.onopen = () => {
        hasOpened = true
        console.log(`Progress stream opened for job ${jobId}`)
        onOpen?.()
      }

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          onMessage(data)
        } catch (error) {
          console.error('Failed to parse progress event:', error)
        }
      }

      eventSource.onerror = (error) => {
        console.error(`Progress stream error for job ${jobId}:`, error)

        // Only close if connection never opened (backend is completely down)
        if (!hasOpened && eventSource.readyState === EventSource.CLOSED) {
          console.error('Failed to establish SSE connection - backend may be unavailable')
          eventSource.close()
        }
        // Otherwise let EventSource handle reconnection automatically

        onError?.(error)
      }

      return eventSource
    } catch (error) {
      console.error('Failed to create EventSource:', error)
      onError?.(error)
      // Return a dummy object with close method to prevent errors
      return { close: () => {} }
    }
  },
}

export default api