import { useState, useEffect, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { progressAPI, uploadAPI } from '../services/api'
import { JOB_STATUS } from '../utils/constants'

/**
 * Hook to stream real-time job progress via Server-Sent Events
 */
export function useJobProgress(jobId, options = {}) {
  const { enabled = true, includeHistory = true } = options

  const [progressData, setProgressData] = useState({
    progress: 0,
    stage: 'queued',
    message: '',
    timestamp: null,
    details: {},
    history: []
  })
  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState(null)
  const [connectionAttempts, setConnectionAttempts] = useState(0)
  const [reconnectTrigger, setReconnectTrigger] = useState(0)

  const eventSourceRef = useRef(null)
  const queryClient = useQueryClient()
  const isMountedRef = useRef(true)
  const MAX_RETRY_ATTEMPTS = 3

  useEffect(() => {
    isMountedRef.current = true

    return () => {
      isMountedRef.current = false
    }
  }, [])

  useEffect(() => {
    console.log(`[SSE] useEffect triggered: jobId=${jobId}, enabled=${enabled}`)

    if (!enabled || !jobId) {
      console.log(`[SSE] Skipping: enabled=${enabled}, jobId=${jobId}`)
      return
    }

    // Clean up previous connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }

    console.log(`[SSE] Starting progress stream for job ${jobId}`)
    setError(null)

    const eventSource = progressAPI.streamProgress(
      jobId,
      // onMessage
      (data) => {
        if (!isMountedRef.current) return

        console.log('Progress update:', data)

        setProgressData(prev => ({
          progress: data.progress || prev.progress,
          stage: data.stage || prev.stage,
          message: data.message || prev.message,
          timestamp: data.timestamp || prev.timestamp,
          details: data.details || prev.details,
          history: includeHistory
            ? [...prev.history, {
                timestamp: data.timestamp,
                stage: data.stage,
                progress: data.progress,
                message: data.message
              }].slice(-50) // Keep last 50 events
            : prev.history
        }))

        // Update the job data in the cache with new progress/status
        queryClient.setQueryData(['job', jobId], (oldData) => {
          if (!oldData) return oldData
          return {
            ...oldData,
            progress: data.progress || oldData.progress,
            current_stage: data.stage || oldData.current_stage,
            status: data.stage === JOB_STATUS.COMPLETED ? JOB_STATUS.COMPLETED :
                    data.stage === JOB_STATUS.FAILED ? JOB_STATUS.FAILED :
                    oldData.status
          }
        })

        // Also update ALL jobs list caches (with different pagination params)
        queryClient.setQueriesData(
          { queryKey: ['jobs'] },
          (oldData) => {
            if (!oldData?.jobs) return oldData
            return {
              ...oldData,
              jobs: oldData.jobs.map(job =>
                job.id === jobId
                  ? {
                      ...job,
                      progress: data.progress || job.progress,
                      current_stage: data.stage || job.current_stage,
                      status: data.stage === JOB_STATUS.COMPLETED ? JOB_STATUS.COMPLETED :
                              data.stage === JOB_STATUS.FAILED ? JOB_STATUS.FAILED :
                              job.status
                    }
                  : job
              )
            }
          }
        )

        // If job completed/failed, invalidate to get full data
        if (data.stage === JOB_STATUS.COMPLETED || data.stage === JOB_STATUS.FAILED) {
          // Invalidate after a short delay to ensure backend has updated
          setTimeout(() => {
            queryClient.invalidateQueries(['job', jobId])
            queryClient.invalidateQueries(['jobs'])
          }, 1000)

          // Close connection after short delay
          setTimeout(() => {
            if (eventSourceRef.current && isMountedRef.current) {
              eventSourceRef.current.close()
              eventSourceRef.current = null
              setIsConnected(false)
            }
          }, 2000)
        }
      },
      // onError
      (error) => {
        if (!isMountedRef.current) return

        console.error('Progress stream error:', error)
        setError(error)

        // EventSource handles reconnection automatically, so we only set disconnected
        // if we've had multiple failures (indicating a real problem)
        setConnectionAttempts(prev => {
          const newAttempts = prev + 1
          if (newAttempts >= MAX_RETRY_ATTEMPTS) {
            setIsConnected(false)
            console.log('Max retry attempts reached, marking as disconnected')
          }
          return newAttempts
        })
      },
      // onOpen
      () => {
        if (!isMountedRef.current) return

        console.log('Progress stream connected')
        setIsConnected(true)
        setError(null)
        setConnectionAttempts(0)
      }
    )

    eventSourceRef.current = eventSource

    // Cleanup on unmount or dependency change
    return () => {
      console.log(`Cleaning up progress stream for job ${jobId}`)

      // Close EventSource
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
        eventSourceRef.current = null
      }

      setIsConnected(false)
    }
  }, [jobId, enabled, includeHistory, reconnectTrigger])

  // Manual reconnection method
  const reconnect = () => {
    // Reset state
    setConnectionAttempts(0)
    setError(null)
    setIsConnected(false)

    // Force close and recreate connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }

    // Trigger re-creation through dependency
    setReconnectTrigger(prev => prev + 1)
  }

  return {
    ...progressData,
    isConnected,
    error,
    connectionAttempts,
    reconnect
  }
}

/**
 * Hook to handle file upload with progress tracking and format selection
 */
export function useUpload() {
  const [uploadProgress, setUploadProgress] = useState(0)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadError, setUploadError] = useState(null)
  const queryClient = useQueryClient()

  /**
   * Upload a file with specified output formats
   * @param {File} file - PDF file to upload
   * @param {Object} options - Upload options
   * @param {string[]} options.outputFormats - Output formats ['msf', 'acc']
   * @param {Object} options.metadata - Additional metadata
   */
  const uploadFile = async (file, options = {}) => {
    setIsUploading(true)
    setUploadProgress(0)
    setUploadError(null)

    try {
      const response = await uploadAPI.upload(file, {
        outputFormats: options.outputFormats || ['msf'],
        metadata: options.metadata,
        onProgress: (progress) => setUploadProgress(progress)
      })

      // Invalidate jobs list to show new job
      queryClient.invalidateQueries(['jobs'])

      setIsUploading(false)
      return response.data
    } catch (error) {
      setUploadError(error)
      setIsUploading(false)
      throw error
    }
  }

  return {
    uploadFile,
    uploadProgress,
    isUploading,
    uploadError
  }
}