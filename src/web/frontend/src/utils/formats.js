import { format, formatDistance, parseISO } from 'date-fns'

/**
 * Format file size in bytes to human readable string
 */
export function formatFileSize(bytes) {
  if (bytes === 0) return '0 Bytes'

  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))

  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

/**
 * Format date for display
 */
export function formatDate(dateString, formatStr = 'MMM dd, yyyy HH:mm') {
  if (!dateString) return 'N/A'
  try {
    const date = typeof dateString === 'string' ? parseISO(dateString) : dateString
    return format(date, formatStr)
  } catch (error) {
    console.warn('Invalid date string:', dateString)
    return 'Invalid Date'
  }
}

/**
 * Format relative time (e.g., "2 minutes ago")
 */
export function formatRelativeTime(dateString) {
  if (!dateString) return 'N/A'
  try {
    const date = typeof dateString === 'string' ? parseISO(dateString) : dateString
    return formatDistance(date, new Date(), { addSuffix: true })
  } catch (error) {
    console.warn('Invalid date string:', dateString)
    return 'Invalid Date'
  }
}

/**
 * Format duration in seconds to human readable string
 */
export function formatDuration(seconds) {
  if (!seconds || seconds < 0) return 'N/A'

  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = Math.floor(seconds % 60)

  if (hours > 0) {
    return `${hours}h ${minutes}m ${secs}s`
  } else if (minutes > 0) {
    return `${minutes}m ${secs}s`
  } else {
    return `${secs}s`
  }
}

/**
 * Format job ID to shorter display version
 */
export function formatJobId(jobId) {
  if (!jobId) return 'N/A'
  return jobId.length > 8 ? `${jobId.substring(0, 8)}...` : jobId
}

/**
 * Truncate filename for display
 */
export function truncateFilename(filename, maxLength = 30) {
  if (!filename) return 'N/A'
  if (filename.length <= maxLength) return filename

  const ext = filename.split('.').pop()
  const name = filename.substring(0, filename.lastIndexOf('.'))
  const truncatedName = name.substring(0, maxLength - ext.length - 4) // -4 for "..." and "."

  return `${truncatedName}...${ext}`
}