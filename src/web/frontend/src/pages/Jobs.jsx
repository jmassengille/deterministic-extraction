import { useState, useMemo, useRef, useEffect } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  Search,
  Filter,
  Trash2,
  FileText,
  ChevronLeft,
  ChevronRight,
  RefreshCw
} from 'lucide-react'
import { useJobs, useDeleteJob } from '../hooks/useJobs'
import StatusBadge from '../components/StatusBadge'
import ConfirmDialog from '../components/ConfirmDialog'
import { formatFileSize, formatRelativeTime, truncateFilename, formatJobId } from '../utils/formats'
import { JOB_STATUS } from '../utils/constants'

export default function Jobs() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [searchQuery, setSearchQuery] = useState(searchParams.get('search') || '')
  const [selectedStatus, setSelectedStatus] = useState(searchParams.get('status') || '')
  const [deleteDialogState, setDeleteDialogState] = useState({ isOpen: false, jobId: null, jobStatus: null })

  const page = parseInt(searchParams.get('page') || '1', 10)
  const limit = 20

  // Debounced search query
  const [debouncedSearch, setDebouncedSearch] = useState(searchQuery)

  // Ref to store timeout ID for cleanup
  const searchTimeoutRef = useRef(null)

  // Update search params when filters change
  const updateFilters = (newFilters) => {
    const params = new URLSearchParams(searchParams)

    Object.entries(newFilters).forEach(([key, value]) => {
      if (value) {
        params.set(key, value)
      } else {
        params.delete(key)
      }
    })

    // Reset to page 1 when filters change
    if (newFilters.search !== undefined || newFilters.status !== undefined) {
      params.delete('page')
    }

    setSearchParams(params)
  }

  // Debounce search input
  const handleSearchChange = (e) => {
    const value = e.target.value
    setSearchQuery(value)

    // Clear previous timeout
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current)
    }

    // Debounce search after 500ms
    searchTimeoutRef.current = setTimeout(() => {
      setDebouncedSearch(value)
      updateFilters({ search: value })
    }, 500)
  }

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (searchTimeoutRef.current) {
        clearTimeout(searchTimeoutRef.current)
      }
    }
  }, [])

  const { data: jobsData, isLoading, error, refetch } = useJobs({
    page,
    limit,
    status: selectedStatus || null,
    search: debouncedSearch || null
  })

  const deleteJobMutation = useDeleteJob()

  const handleStatusFilter = (status) => {
    const newStatus = status === selectedStatus ? '' : status
    setSelectedStatus(newStatus)
    updateFilters({ status: newStatus })
  }

  const handlePageChange = (newPage) => {
    const params = new URLSearchParams(searchParams)
    if (newPage > 1) {
      params.set('page', newPage.toString())
    } else {
      params.delete('page')
    }
    setSearchParams(params)
  }

  const handleDeleteClick = (jobId, jobStatus) => {
    setDeleteDialogState({ isOpen: true, jobId, jobStatus })
  }

  const handleDeleteConfirm = async () => {
    try {
      await deleteJobMutation.mutateAsync(deleteDialogState.jobId)
    } catch (error) {
      console.error('Failed to delete job:', error)
    }
  }

  const statusFilters = [
    { key: '', label: 'All', count: jobsData?.total || 0 },
    { key: JOB_STATUS.PENDING, label: 'Pending' },
    { key: JOB_STATUS.PROCESSING, label: 'Processing' },
    { key: JOB_STATUS.COMPLETED, label: 'Completed' },
    { key: JOB_STATUS.FAILED, label: 'Failed' }
  ]

  return (
    <div>
      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Jobs</h1>
          <p className="mt-1 text-sm text-gray-600">
            Monitor and manage PDF processing jobs
          </p>
        </div>
        <button
          onClick={() => refetch()}
          className="flex items-center px-3 py-2 text-sm bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors cursor-pointer"
          disabled={isLoading}
        >
          <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg border border-slate-200 p-4 mb-6">
        <div className="flex flex-col sm:flex-row gap-4">
          {/* Search */}
          <div className="flex-1">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-slate-400" />
              <input
                type="text"
                placeholder="Search by filename..."
                value={searchQuery}
                onChange={handleSearchChange}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
          </div>

          {/* Status Filter */}
          <div className="flex gap-2">
            {statusFilters.map((filter) => (
              <button
                key={filter.key}
                onClick={() => handleStatusFilter(filter.key)}
                className={`px-3 py-2 text-sm font-medium rounded-md transition-colors cursor-pointer ${
                  selectedStatus === filter.key
                    ? 'bg-blue-100 text-blue-700 border-blue-200'
                    : 'bg-gray-50 text-gray-600 border-gray-200 hover:bg-gray-100'
                } border`}
              >
                {filter.label}
                {filter.count !== undefined && (
                  <span className="ml-2 px-1.5 py-0.5 bg-slate-200 text-slate-600 text-xs rounded">
                    {filter.count}
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Jobs List */}
      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
        {error ? (
          <div className="p-6 text-center">
            <div className="text-red-500 text-sm">
              Failed to load jobs: {error.message}
            </div>
            <button
              onClick={() => refetch()}
              className="mt-2 text-blue-600 hover:text-blue-700 text-sm cursor-pointer"
            >
              Try Again
            </button>
          </div>
        ) : isLoading ? (
          <div className="p-6">
            <div className="space-y-4">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="animate-pulse">
                  <div className="flex items-center space-x-4">
                    <div className="w-8 h-8 bg-slate-200 rounded" />
                    <div className="flex-1 space-y-2">
                      <div className="h-4 bg-slate-200 rounded w-1/3" />
                      <div className="h-3 bg-slate-200 rounded w-1/4" />
                    </div>
                    <div className="w-20 h-6 bg-slate-200 rounded" />
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : jobsData?.jobs?.length > 0 ? (
          <>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Job
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      File
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Created
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 bg-white">
                  {jobsData.jobs.map((job) => (
                    <tr key={job.id} className="hover:bg-slate-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center">
                          <FileText className="h-4 w-4 text-gray-400 mr-2 flex-shrink-0" />
                          <Link
                            to={`/jobs/${job.id}`}
                            className="text-sm font-mono text-blue-600 hover:text-blue-700 cursor-pointer"
                          >
                            {formatJobId(job.id)}
                          </Link>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div>
                          <p className="text-sm font-medium text-gray-900">
                            {job.filename}
                          </p>
                          <p className="text-xs text-gray-500 mt-1">
                            {formatFileSize(job.file_size)}
                          </p>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center gap-2">
                          <StatusBadge status={job.status} />
                          {job.progress > 0 && job.status === JOB_STATUS.PROCESSING && (
                            <span className="text-xs text-gray-500">
                              {job.progress}%
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {formatRelativeTime(job.created_at)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center justify-end gap-2">
                          <Link
                            to={`/jobs/${job.id}`}
                            className="px-3 py-1 text-xs bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors cursor-pointer"
                          >
                            Details
                          </Link>
                          <button
                            onClick={() => handleDeleteClick(job.id, job.status)}
                            disabled={deleteJobMutation.isLoading}
                            className="p-1.5 text-red-600 hover:bg-red-50 rounded-lg transition-colors cursor-pointer disabled:cursor-not-allowed"
                            title="Delete Job"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {jobsData.pages > 1 && (
              <div className="px-4 py-3 border-t border-slate-200 flex items-center justify-between">
                <div className="text-sm text-slate-500">
                  Showing {((page - 1) * limit) + 1} to {Math.min(page * limit, jobsData.total)} of {jobsData.total} jobs
                </div>
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => handlePageChange(page - 1)}
                    disabled={page === 1}
                    className="p-2 text-gray-600 hover:bg-gray-50 rounded cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </button>
                  <span className="px-3 py-1 text-sm bg-blue-50 text-blue-600 rounded">
                    {page} of {jobsData.pages}
                  </span>
                  <button
                    onClick={() => handlePageChange(page + 1)}
                    disabled={page >= jobsData.pages}
                    className="p-2 text-gray-600 hover:bg-gray-50 rounded cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <ChevronRight className="h-4 w-4" />
                  </button>
                </div>
              </div>
            )}
          </>
        ) : (
          <div className="p-6 text-center text-gray-500">
            {debouncedSearch || selectedStatus ? (
              <>
                No jobs found matching your criteria — try adjusting your filters.
                {' '}
                <button
                  onClick={() => {
                    setSearchQuery('')
                    setSelectedStatus('')
                    setDebouncedSearch('')
                    updateFilters({ search: '', status: '' })
                  }}
                  className="ml-2 text-blue-600 hover:text-blue-700 cursor-pointer"
                >
                  Clear filters
                </button>
              </>
            ) : (
              'No jobs yet — upload a PDF to get started.'
            )}
          </div>
        )}
      </div>

      <ConfirmDialog
        isOpen={deleteDialogState.isOpen}
        onClose={() => setDeleteDialogState({ isOpen: false, jobId: null, jobStatus: null })}
        onConfirm={handleDeleteConfirm}
        title={deleteDialogState.jobStatus === JOB_STATUS.PENDING || deleteDialogState.jobStatus === JOB_STATUS.PROCESSING ? 'Cancel Job' : 'Delete Job'}
        message={
          deleteDialogState.jobStatus === JOB_STATUS.PENDING || deleteDialogState.jobStatus === JOB_STATUS.PROCESSING
            ? 'Are you sure you want to cancel this job? This will stop the processing and remove the job from the queue.'
            : 'Are you sure you want to delete this job? This action cannot be undone.'
        }
        confirmText={deleteDialogState.jobStatus === JOB_STATUS.PENDING || deleteDialogState.jobStatus === JOB_STATUS.PROCESSING ? 'Cancel Job' : 'Delete'}
        cancelText="Keep Job"
        variant="danger"
      />
    </div>
  )
}