import { Link } from 'react-router-dom'
import PropTypes from 'prop-types'
import {
  Upload,
  List,
  FileText,
  Zap,
  CheckCircle,
  XCircle,
  Clock,
  Activity,
  HardDrive,
  AlertTriangle
} from 'lucide-react'
import { useHealthStatus } from '../hooks/useHealth'
import { useJobStats } from '../hooks/useJobs'
import StatusBadge from '../components/StatusBadge'
import FadeIn from '../components/FadeIn'
import { formatFileSize, formatRelativeTime, truncateFilename } from '../utils/formats'

export default function Dashboard() {
  const { isHealthy, isLoading: healthLoading, health, systemStatus } = useHealthStatus()
  const { stats, recentJobs, isLoading: jobsLoading } = useJobStats()

  return (
    <div className="max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-gray-900">Dashboard</h1>
        <p className="mt-2 text-sm text-gray-600">
          Monitor your document processing pipeline
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4 mb-8">
        <FadeIn delay={0}>
          <StatCard
            title="Total Jobs"
            value={stats.total}
            icon={FileText}
            color="slate"
            loading={jobsLoading}
          />
        </FadeIn>
        <FadeIn delay={0.1}>
          <StatCard
            title="Active Jobs"
            value={stats.active}
            icon={Zap}
            color="primary"
            loading={jobsLoading}
          />
        </FadeIn>
        <FadeIn delay={0.2}>
          <StatCard
            title="Completed"
            value={stats.completed}
            icon={CheckCircle}
            color="green"
            loading={jobsLoading}
          />
        </FadeIn>
        <FadeIn delay={0.3}>
          <StatCard
            title="Failed"
            value={stats.failed}
            icon={XCircle}
            color="red"
            loading={jobsLoading}
          />
        </FadeIn>
      </div>

      {/* System Health & Storage */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* System Health */}
        <FadeIn delay={0.2}>
          <div className="bg-white rounded-xl p-4 shadow-sm">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">System Health</h2>
            <div className="space-y-2">
              <HealthItem
                name="API Server"
                status={systemStatus}
                loading={healthLoading}
              />
              <HealthItem
                name="Worker Manager"
                status={health?.worker_stats?.active_workers > 0 ? 'online' : 'offline'}
                loading={healthLoading}
              />
              {health?.worker_stats && (
                <div className="text-sm text-gray-600 mt-3 font-medium">
                  {health.worker_stats.queue_count || 0} jobs queued
                </div>
              )}
            </div>
          </div>
        </FadeIn>

        {/* Storage Info */}
        <FadeIn delay={0.3}>
          <div className="bg-white rounded-xl p-4 shadow-sm">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Storage Health</h2>
            {health?.storage ? (
              <StorageDisplay storage={health.storage} />
            ) : (
              <div className="text-sm text-gray-500">
                Storage information not available
              </div>
            )}
          </div>
        </FadeIn>
      </div>

      {/* Quick Actions */}
      <FadeIn delay={0.4}>
        <div className="bg-white rounded-xl p-6 mb-8 shadow-sm">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Quick Actions</h2>
          <div className="grid grid-cols-2 gap-4">
            <Link
              to="/upload"
              className="flex flex-col items-center p-6 bg-white border-2 border-slate-200 rounded-xl hover:border-blue-500 hover:shadow-lg transition-all duration-200 hover:scale-[1.02] cursor-pointer group focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
            >
              <div className="h-12 w-12 mb-3 bg-blue-50 rounded-lg flex items-center justify-center group-hover:bg-blue-100 transition-colors">
                <Upload className="h-6 w-6 text-blue-600" />
              </div>
              <span className="text-sm font-semibold text-gray-900">Upload PDF</span>
              <span className="text-xs text-gray-500 mt-1">Process new document</span>
            </Link>
            <Link
              to="/jobs"
              className="flex flex-col items-center p-6 bg-white border-2 border-slate-200 rounded-xl hover:border-blue-500 hover:shadow-lg transition-all duration-200 hover:scale-[1.02] cursor-pointer group focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
            >
              <div className="h-12 w-12 mb-3 bg-slate-50 rounded-lg flex items-center justify-center group-hover:bg-slate-100 transition-colors">
                <List className="h-6 w-6 text-slate-700" />
              </div>
              <span className="text-sm font-semibold text-gray-900">View Jobs</span>
              <span className="text-xs text-gray-500 mt-1">Monitor processing</span>
            </Link>
          </div>
        </div>
      </FadeIn>

      {/* Recent Jobs */}
      <FadeIn delay={0.5}>
        <div className="bg-white rounded-xl p-4 shadow-sm">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-semibold text-gray-900">Recent Jobs</h2>
            <Link to="/jobs" className="text-sm text-accent-600 hover:text-accent-700 font-medium cursor-pointer">
              View all →
            </Link>
          </div>
          <div className="space-y-4">
            {jobsLoading ? (
              <div className="text-sm text-gray-500">Loading jobs...</div>
            ) : recentJobs.length > 0 ? (
              recentJobs.map((job) => (
                <div key={job.id} className="flex items-center justify-between p-3 rounded-lg bg-gray-50 hover:bg-gray-100 transition-all duration-200 hover:shadow-sm">
                  <div className="flex items-center">
                    <div className="p-2 bg-white rounded mr-3">
                      <FileText className="h-5 w-5 text-gray-500" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-gray-900">
                        {truncateFilename(job.filename, 40)}
                      </p>
                      <div className="flex items-center space-x-2 text-xs text-gray-500 mt-1">
                        <span>{formatFileSize(job.file_size)}</span>
                        <span>•</span>
                        <span>{formatRelativeTime(job.created_at)}</span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center space-x-3">
                    <StatusBadge status={job.status} />
                    {(job.status === 'completed' || job.status === 'failed') && (
                      <Link
                        to={`/jobs/${job.id}`}
                        className="text-xs text-accent-600 hover:text-accent-700 font-medium px-2 py-1 bg-accent-50 rounded hover:bg-accent-100 transition-all duration-200 cursor-pointer"
                      >
                        Details
                      </Link>
                    )}
                  </div>
                </div>
              ))
            ) : (
              <div className="text-center py-8">
                <FileText className="h-12 w-12 text-slate-300 mx-auto mb-3" />
                <p className="text-sm text-gray-500">No recent jobs — upload a PDF to get started</p>
              </div>
            )}
          </div>
        </div>
      </FadeIn>
    </div>
  )
}

// Helper Components
function StatCard({ title, value, icon: Icon, color, loading }) {
  const colorClasses = {
    slate: 'bg-gray-50 text-gray-600 border-gray-200',
    primary: 'bg-blue-50 text-blue-600 border-blue-200',
    green: 'bg-green-50 text-green-600 border-green-200',
    red: 'bg-red-50 text-red-600 border-red-200',
  }

  return (
    <div className="bg-white rounded-xl p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-600">{title}</p>
          {loading ? (
            <div className="h-8 w-12 bg-slate-200 rounded animate-pulse mt-1" />
          ) : (
            <p className="text-2xl font-bold text-gray-900 mt-1">{value}</p>
          )}
        </div>
        <Icon className="h-5 w-5 text-gray-400" />
      </div>
    </div>
  )
}

StatCard.propTypes = {
  title: PropTypes.string.isRequired,
  value: PropTypes.number,
  icon: PropTypes.elementType.isRequired,
  color: PropTypes.oneOf(['slate', 'primary', 'green', 'red']).isRequired,
  loading: PropTypes.bool
}

function HealthItem({ name, status, loading }) {
  if (loading) {
    return (
      <div className="flex items-center justify-between py-1.5">
        <span className="text-sm font-medium text-slate-700">{name}</span>
        <div className="h-5 w-16 bg-slate-200 rounded animate-pulse" />
      </div>
    )
  }

  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="text-sm font-medium text-slate-700">{name}</span>
      <div className="flex items-center">
        <div className={`w-2 h-2 rounded-full mr-1.5 ${
          status === 'online' ? 'bg-green-500' :
          status === 'degraded' ? 'bg-yellow-500' : 'bg-red-500'
        }`} />
        <span className={`text-sm font-semibold ${
          status === 'online' ? 'text-green-700' :
          status === 'degraded' ? 'text-yellow-700' : 'text-red-700'
        }`}>
          {status}
        </span>
      </div>
    </div>
  )
}

HealthItem.propTypes = {
  name: PropTypes.string.isRequired,
  status: PropTypes.oneOf(['online', 'offline', 'degraded']).isRequired,
  loading: PropTypes.bool
}

function StorageDisplay({ storage }) {
  return (
    <div className="space-y-4">
      {storage.disk_usage_gb !== undefined && storage.disk_total_gb !== undefined && (
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-slate-700">
              <HardDrive className="inline w-4 h-4 mr-1.5" />
              Disk Usage
            </span>
            <span className="text-sm font-semibold text-gray-700">
              {storage.disk_usage_gb.toFixed(1)} / {storage.disk_total_gb} GB
            </span>
          </div>
          <div className="w-full bg-slate-200 rounded-full h-2">
            <div
              className="h-full rounded-full bg-primary-500"
              style={{
                width: `${Math.min((storage.disk_usage_gb / storage.disk_total_gb) * 100, 100)}%`
              }}
            />
          </div>
        </div>
      )}

      {storage.total_workers !== undefined && (
        <div className="flex items-center justify-between py-1">
          <span className="text-sm font-medium text-slate-700">
            <Activity className="inline w-4 h-4 mr-1.5" />
            Total Workers
          </span>
          <span className="text-sm font-semibold text-gray-700">{storage.total_workers}</span>
        </div>
      )}

      {storage.max_concurrent_llm !== undefined && (
        <div className="flex items-center justify-between py-1">
          <span className="text-sm font-medium text-slate-700">
            <Zap className="inline w-4 h-4 mr-1.5" />
            Concurrent LLM Limit
          </span>
          <span className="text-sm font-semibold text-gray-700">{storage.max_concurrent_llm}</span>
        </div>
      )}
    </div>
  )
}

StorageDisplay.propTypes = {
  storage: PropTypes.shape({
    disk_usage_gb: PropTypes.number,
    disk_total_gb: PropTypes.number,
    total_workers: PropTypes.number,
    max_concurrent_llm: PropTypes.number
  }).isRequired
}