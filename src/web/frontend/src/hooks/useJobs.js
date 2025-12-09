import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { jobsAPI } from '../services/api'
import { POLLING_INTERVALS } from '../utils/constants'
import { getErrorMessage } from '../utils/errorHandling'

/**
 * Hook to fetch jobs list with pagination and filtering
 */
export function useJobs(params = {}) {
  const {
    page = 1,
    limit = 20,
    status = null,
    search = null,
    enablePolling = true
  } = params

  return useQuery({
    queryKey: ['jobs', { page, limit, status, search }],
    queryFn: async () => {
      const queryParams = { page, limit }
      if (status) queryParams.status = status
      if (search) queryParams.search = search

      const response = await jobsAPI.list(queryParams)
      return response.data
    },
    refetchInterval: enablePolling ? POLLING_INTERVALS.JOB_LIST : false,
    keepPreviousData: true,
    staleTime: 3000,
    onError: (error) => {
      console.error('Failed to fetch jobs:', error)
      toast.error(getErrorMessage(error), {
        description: 'Unable to load jobs list'
      })
    }
  })
}

/**
 * Hook to fetch a single job by ID
 */
export function useJob(jobId, options = {}) {
  const { enabled = true, refetchInterval = false } = options

  return useQuery({
    queryKey: ['job', jobId],
    queryFn: async () => {
      const response = await jobsAPI.get(jobId)
      return response.data
    },
    enabled: enabled && Boolean(jobId),
    staleTime: 2000,
    refetchInterval: refetchInterval,
    onError: (error) => {
      console.error(`Failed to fetch job ${jobId}:`, error)
      toast.error(getErrorMessage(error), {
        description: 'Unable to load job details'
      })
    }
  })
}

/**
 * Hook to delete/cancel a job
 */
export function useDeleteJob() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (jobId) => jobsAPI.delete(jobId),
    onSuccess: (_, jobId) => {
      queryClient.invalidateQueries(['jobs'])
      queryClient.removeQueries(['job', jobId])
      toast.success('Job deleted successfully')
    },
    onError: (error) => {
      console.error('Failed to delete job:', error)
      toast.error(getErrorMessage(error), {
        description: 'Unable to delete job'
      })
    }
  })
}

/**
 * Hook to download file from completed job (supports MSF and ACC formats)
 */
export function useDownloadFile() {
  return useMutation({
    mutationFn: async ({ jobId, format = 'msf', interval = null }) => {
      try {
        const response = await jobsAPI.download(jobId, format, interval)

        // Determine MIME type based on format
        const mimeType = format === 'acc' ? 'text/plain' : 'application/xml'
        const blob = new Blob([response.data], { type: mimeType })
        const url = window.URL.createObjectURL(blob)

        // Get filename from Content-Disposition header or use default
        const contentDisposition = response.headers['content-disposition']
        let filename = format === 'acc' ? 'output.acc' : 'output.msf'
        if (contentDisposition) {
          const match = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/)
          if (match && match[1]) {
            filename = match[1].replace(/['"]/g, '')
          }
        }

        // Trigger download
        const link = document.createElement('a')
        link.href = url
        link.download = filename
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)

        // Cleanup blob URL after a short delay
        setTimeout(() => {
          window.URL.revokeObjectURL(url)
        }, 100)

        return { success: true, filename, format }
      } catch (error) {
        console.error('Download preparation failed:', error)
        throw error
      }
    },
    onSuccess: (data) => {
      console.log(`${data.format.toUpperCase()} file downloaded: ${data.filename}`)
      toast.success(`${data.format.toUpperCase()} file downloaded`, {
        description: data.filename
      })
    },
    onError: (error) => {
      console.error('Failed to download file:', error)
      toast.error(getErrorMessage(error), {
        description: 'Unable to download file'
      })
    }
  })
}

/**
 * Hook to download MSF file (backward compatible alias)
 * @deprecated Use useDownloadFile instead
 */
export function useDownloadMsf() {
  const downloadFile = useDownloadFile()
  return {
    ...downloadFile,
    mutateAsync: (jobId) => downloadFile.mutateAsync({ jobId, format: 'msf' })
  }
}

/**
 * Hook to get available download formats for a job
 */
export function useAvailableFormats(jobId) {
  return useQuery({
    queryKey: ['job-formats', jobId],
    queryFn: async () => {
      const response = await jobsAPI.getFormats(jobId)
      return response.data
    },
    enabled: Boolean(jobId),
    staleTime: 30000
  })
}

/**
 * Hook for job statistics and summary data
 */
export function useJobStats() {
  const { data: jobsData } = useJobs({ page: 1, limit: 100, enablePolling: true })

  const stats = {
    total: jobsData?.total || 0,
    active: 0,
    completed: 0,
    failed: 0,
    pending: 0
  }

  if (jobsData?.jobs) {
    jobsData.jobs.forEach(job => {
      switch (job.status) {
        case 'processing':
          stats.active++
          break
        case 'completed':
          stats.completed++
          break
        case 'failed':
          stats.failed++
          break
        case 'pending':
          stats.pending++
          break
      }
    })
  }

  return {
    stats,
    recentJobs: jobsData?.jobs?.slice(0, 5) || [],
    isLoading: !jobsData
  }
}