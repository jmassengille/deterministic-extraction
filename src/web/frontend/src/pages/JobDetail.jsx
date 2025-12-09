import { useState, useEffect } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  RefreshCw,
  FileText,
  Clock,
  AlertTriangle,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Activity,
  Trash2,
  FileEdit
} from 'lucide-react'
import { useJob, useDeleteJob, useDownloadFile } from '../hooks/useJobs'
import { useJobProgress } from '../hooks/useJobProgress'
import StatusBadge from '../components/StatusBadge'
import ConfirmDialog from '../components/ConfirmDialog'
import { formatFileSize, formatDate, formatDuration, formatRelativeTime } from '../utils/formats'
import { JOB_STATUS, STAGE_LABELS } from '../utils/constants'

export default function JobDetail() {
  const { jobId } = useParams()
  const navigate = useNavigate()
  const [showLogs, setShowLogs] = useState(false)
  const [sseEnabled, setSseEnabled] = useState(true)
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)

  // First fetch the job data
  const { data: job, isLoading, error, refetch } = useJob(jobId)

  // Then setup SSE based on job status
  const {
    progress,
    stage,
    message,
    timestamp,
    history,
    isConnected,
    error: progressError,
    connectionAttempts,
    reconnect
  } = useJobProgress(jobId, {
    enabled: sseEnabled && job?.status === JOB_STATUS.PROCESSING
  })

  // Use effect to enable polling when SSE is disconnected
  useEffect(() => {
    if (job?.status === JOB_STATUS.PROCESSING && !isConnected && sseEnabled) {
      const interval = setInterval(() => {
        refetch()
      }, 2000)
      return () => clearInterval(interval)
    }
  }, [job?.status, isConnected, sseEnabled, refetch])

  const deleteJobMutation = useDeleteJob()
  const downloadFileMutation = useDownloadFile()

  const handleDeleteClick = () => {
    setShowDeleteDialog(true)
  }

  const handleDeleteConfirm = async () => {
    try {
      await deleteJobMutation.mutateAsync(jobId)
      navigate('/jobs')
    } catch (error) {
      console.error('Failed to delete job:', error)
    }
  }

  const handleDownload = async (format, key = null) => {
    try {
      await downloadFileMutation.mutateAsync({ jobId, format, key })
    } catch (error) {
      console.error(`Failed to download ${format.toUpperCase()}:`, error)
    }
  }

  if (isLoading) {
    return (
      <div className="animate-pulse">
        <div className="flex items-center mb-6">
          <div className="w-24 h-6 bg-slate-200 rounded mr-4" />
          <div className="w-64 h-8 bg-slate-200 rounded" />
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            <div className="h-32 bg-slate-200 rounded-lg" />
            <div className="h-64 bg-slate-200 rounded-lg" />
          </div>
          <div className="h-96 bg-slate-200 rounded-lg" />
        </div>
      </div>
    )
  }

  if (error || !job) {
    return (
      <div className="text-center py-12">
        <AlertTriangle className="h-12 w-12 text-red-500 mx-auto mb-4" />
        <h2 className="text-xl font-semibold text-slate-900 mb-2">Job Not Found</h2>
        <p className="text-slate-600 mb-4">
          The requested job could not be found or an error occurred.
        </p>
        <Link
          to="/jobs"
          className="text-blue-600 hover:text-blue-700 font-medium cursor-pointer"
        >
          ← Back to Jobs
        </Link>
      </div>
    )
  }

  // Use SSE progress when connected and has valid data, otherwise fallback to REST API progress
  const currentProgress = job.status === JOB_STATUS.PROCESSING && isConnected && progress > 0
    ? progress
    : job.progress || 0

  const currentStage = job.status === JOB_STATUS.PROCESSING && isConnected && stage !== 'queued'
    ? stage
    : job.current_stage || 'queued'

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center">
          <Link
            to="/jobs"
            className="flex items-center text-slate-600 hover:text-slate-800 mr-4"
          >
            <ArrowLeft className="h-4 w-4 mr-1" />
            Jobs
          </Link>
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">
              Job Details
            </h1>
            <p className="text-sm text-slate-600 font-mono">
              {jobId}
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={handleDeleteClick}
            disabled={deleteJobMutation.isLoading}
            className="flex items-center px-4 py-2 bg-white border-2 border-red-300 text-red-600 rounded-lg hover:border-red-400 hover:bg-red-50 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:ring-offset-2"
          >
            <Trash2 className="h-4 w-4 mr-2" />
            {job.status === JOB_STATUS.PENDING || job.status === JOB_STATUS.PROCESSING ? 'Cancel Job' : 'Delete Job'}
          </button>

          <button
            onClick={() => refetch()}
            className="p-2 text-slate-600 hover:bg-slate-100 rounded transition-colors cursor-pointer"
            title="Refresh"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Job Overview */}
          <div className="bg-white rounded-lg border border-slate-200 p-6">
            <h2 className="text-lg font-semibold text-slate-900 mb-4">Overview</h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <dt className="text-sm font-medium text-slate-500">Filename</dt>
                <dd className="mt-1 text-sm text-slate-900 font-medium">
                  {job.filename}
                </dd>
              </div>

              <div>
                <dt className="text-sm font-medium text-slate-500">File Size</dt>
                <dd className="mt-1 text-sm text-slate-900">
                  {formatFileSize(job.file_size)}
                </dd>
              </div>

              <div>
                <dt className="text-sm font-medium text-slate-500">Status</dt>
                <dd className="mt-1">
                  <StatusBadge status={job.status} />
                </dd>
              </div>

              <div>
                <dt className="text-sm font-medium text-slate-500">Created</dt>
                <dd className="mt-1 text-sm text-slate-900">
                  {formatDate(job.created_at)}
                  <span className="text-slate-500 ml-2">
                    ({formatRelativeTime(job.created_at)})
                  </span>
                </dd>
              </div>

              {job.started_at && (
                <div>
                  <dt className="text-sm font-medium text-slate-500">Started</dt>
                  <dd className="mt-1 text-sm text-slate-900">
                    {formatDate(job.started_at)}
                  </dd>
                </div>
              )}

              {job.completed_at && (
                <div>
                  <dt className="text-sm font-medium text-slate-500">Completed</dt>
                  <dd className="mt-1 text-sm text-slate-900">
                    {formatDate(job.completed_at)}
                    {job.duration && (
                      <span className="text-slate-500 ml-2">
                        ({formatDuration(job.duration)})
                      </span>
                    )}
                  </dd>
                </div>
              )}
            </div>
          </div>

          {/* Progress */}
          {(job.status === JOB_STATUS.PROCESSING || currentProgress > 0) && (
            <div className="bg-white rounded-lg border border-slate-200 p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-slate-900">Progress</h2>
                {job.status === JOB_STATUS.PROCESSING && (
                  <div className="flex items-center text-sm space-x-4">
                    {sseEnabled ? (
                      <>
                        {isConnected ? (
                          <div className="flex items-center text-green-600">
                            <div className="w-2 h-2 bg-green-500 rounded-full mr-2" />
                            Live Updates
                          </div>
                        ) : progressError && connectionAttempts >= 3 ? (
                          <div className="flex items-center text-gray-500">
                            <AlertTriangle className="h-4 w-4 mr-2" />
                            Backend Unavailable
                            <button
                              onClick={() => setSseEnabled(false)}
                              className="ml-2 text-xs text-slate-600 hover:text-slate-700 cursor-pointer"
                            >
                              Disable Live Updates
                            </button>
                          </div>
                        ) : (
                          <div className="flex items-center text-gray-500">
                            <Activity className="h-4 w-4 mr-2 animate-pulse" />
                            Polling for Updates
                          </div>
                        )}
                      </>
                    ) : (
                      <div className="flex items-center text-slate-500">
                        <div className="w-2 h-2 bg-slate-400 rounded-full mr-2" />
                        Live Updates Disabled
                        <button
                          onClick={() => {
                            setSseEnabled(true)
                            reconnect()
                          }}
                          className="ml-2 text-blue-600 hover:text-blue-700 cursor-pointer"
                        >
                          Enable
                        </button>
                      </div>
                    )}
                    <button
                      onClick={() => refetch()}
                      className="p-1 text-slate-600 hover:bg-slate-100 rounded cursor-pointer"
                      title="Refresh"
                    >
                      <RefreshCw className="h-3 w-3" />
                    </button>
                  </div>
                )}
              </div>

              <div className="mb-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-slate-700">
                    {STAGE_LABELS[currentStage] || 'Processing'}
                  </span>
                  <span className="text-sm text-slate-600">
                    {currentProgress}%
                  </span>
                </div>
                <div className="w-full bg-slate-200 rounded-full h-2">
                  <div
                    className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${currentProgress}%` }}
                  />
                </div>
              </div>

              {message && (
                <div className="text-sm text-slate-600">
                  Current: {message}
                </div>
              )}

              {timestamp && (
                <div className="text-xs text-slate-500 mt-2">
                  Last update: {formatDate(timestamp, 'HH:mm:ss')}
                </div>
              )}
            </div>
          )}

          {/* Error Details */}
          {job.status === JOB_STATUS.FAILED && job.error && (
            <div className="bg-white rounded-lg border border-red-200 p-6">
              <div className="flex items-center mb-4">
                <AlertTriangle className="h-5 w-5 text-red-500 mr-2" />
                <h2 className="text-lg font-semibold text-red-900">Error Details</h2>
              </div>
              <div className="bg-red-50 rounded-lg p-4">
                <pre className="text-sm text-red-800 whitespace-pre-wrap">
                  {job.error}
                </pre>
              </div>
            </div>
          )}

          {/* Success Message */}
          {job.status === JOB_STATUS.COMPLETED && (
            <div className="bg-white rounded-lg border border-green-200 p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center">
                  <CheckCircle className="h-5 w-5 text-green-500 mr-2" />
                  <h2 className="text-lg font-semibold text-green-900">Processing Complete</h2>
                </div>
              </div>
              <div className="bg-green-50 rounded-lg p-4">
                <p className="text-sm text-green-800">
                  Your document has been successfully processed.
                  You can now download the generated files.
                </p>
                {job.output_paths && Object.keys(job.output_paths).length > 0 && (
                  <div className="mt-2 text-xs text-green-600">
                    Output formats: {Object.keys(job.output_paths).join(', ')}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Processing Logs */}
          {(history?.length > 0 || job.status === JOB_STATUS.PROCESSING) && (
            <div className="bg-white rounded-lg border border-slate-200">
              <div className="p-4 border-b border-slate-200">
                <button
                  onClick={() => setShowLogs(!showLogs)}
                  className="flex items-center justify-between w-full text-left"
                >
                  <h3 className="text-sm font-semibold text-slate-900">
                    Processing Logs
                  </h3>
                  {showLogs ? (
                    <ChevronUp className="h-4 w-4" />
                  ) : (
                    <ChevronDown className="h-4 w-4" />
                  )}
                </button>
              </div>

              {showLogs && (
                <div className="p-4 max-h-96 overflow-y-auto">
                  {history?.length > 0 ? (
                    <div className="space-y-2">
                      {history.map((entry, index) => (
                        <div key={index} className="text-xs">
                          <div className="flex items-start space-x-2">
                            <span className="text-slate-400 shrink-0">
                              {formatDate(entry.timestamp, 'HH:mm:ss')}
                            </span>
                            <div className="flex-1">
                              <div className="text-slate-600">
                                {STAGE_LABELS[entry.stage] || entry.stage}
                              </div>
                              {entry.message && (
                                <div className="text-slate-500 mt-1">
                                  {entry.message}
                                </div>
                              )}
                              {entry.progress !== undefined && (
                                <div className="text-slate-400">
                                  {entry.progress}%
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-sm text-slate-500 text-center py-4">
                      No log entries yet
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Processing Results */}
          {job.status === JOB_STATUS.COMPLETED && job.metadata && (
            <>
              {/* Document Info */}
              {job.metadata.document_info && (
                <div className="bg-white rounded-lg border border-slate-200 p-4">
                  <h3 className="text-sm font-semibold text-slate-900 mb-3">Document Details</h3>
                  <div className="space-y-2">
                    {Object.entries(job.metadata.document_info).map(([key, value]) => (
                      value && (
                        <div key={key}>
                          <dt className="text-xs font-medium text-slate-500 capitalize">{key.replace(/_/g, ' ')}</dt>
                          <dd className="text-sm text-slate-900">{String(value)}</dd>
                        </div>
                      )
                    ))}
                  </div>
                </div>
              )}

              {/* Processing Statistics */}
              {job.metadata.statistics && (
                <div className="bg-white rounded-lg border border-slate-200 p-4">
                  <h3 className="text-sm font-semibold text-slate-900 mb-3">Processing Statistics</h3>
                  <div className="grid grid-cols-2 gap-4">
                    {job.metadata.statistics.pages_analyzed !== undefined && (
                      <div>
                        <dt className="text-xs font-medium text-slate-500">Pages Analyzed</dt>
                        <dd className="text-lg font-semibold text-slate-900">{job.metadata.statistics.pages_analyzed}</dd>
                      </div>
                    )}
                    {job.metadata.statistics.tables_found !== undefined && (
                      <div>
                        <dt className="text-xs font-medium text-slate-500">Tables Found</dt>
                        <dd className="text-lg font-semibold text-slate-900">{job.metadata.statistics.tables_found}</dd>
                      </div>
                    )}
                    {job.metadata.statistics.tables_processed !== undefined && (
                      <div>
                        <dt className="text-xs font-medium text-slate-500">Tables Processed</dt>
                        <dd className="text-lg font-semibold text-slate-900">{job.metadata.statistics.tables_processed}</dd>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      <ConfirmDialog
        isOpen={showDeleteDialog}
        onClose={() => setShowDeleteDialog(false)}
        onConfirm={handleDeleteConfirm}
        title={job.status === JOB_STATUS.PENDING || job.status === JOB_STATUS.PROCESSING ? 'Cancel Job' : 'Delete Job'}
        message={
          job.status === JOB_STATUS.PENDING || job.status === JOB_STATUS.PROCESSING
            ? 'Are you sure you want to cancel this job? This will stop the processing and remove the job from the queue.'
            : 'Are you sure you want to delete this job? This action cannot be undone.'
        }
        confirmText={job.status === JOB_STATUS.PENDING || job.status === JOB_STATUS.PROCESSING ? 'Cancel Job' : 'Delete'}
        cancelText="Keep Job"
        variant="danger"
      />
    </div>
  )
}