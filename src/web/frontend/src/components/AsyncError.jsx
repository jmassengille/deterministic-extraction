import { AlertCircle, RefreshCw, WifiOff, ServerCrash } from 'lucide-react'
import PropTypes from 'prop-types'
import { motion } from 'framer-motion'
import { getErrorMessage, isNetworkError, isServerError } from '../utils/errorHandling'

const VARIANT_STYLES = {
  network: {
    container: 'bg-amber-50 border-amber-900/20',
    title: 'text-amber-900',
    message: 'text-amber-700',
    icon: 'text-amber-500',
    button: 'text-amber-900 hover:bg-white/50',
    IconComponent: WifiOff
  },
  server: {
    container: 'bg-red-50 border-red-900/20',
    title: 'text-red-900',
    message: 'text-red-700',
    icon: 'text-red-500',
    button: 'text-red-900 hover:bg-white/50',
    IconComponent: ServerCrash
  },
  default: {
    container: 'bg-red-50 border-red-900/20',
    title: 'text-red-900',
    message: 'text-red-700',
    icon: 'text-red-500',
    button: 'text-red-900 hover:bg-white/50',
    IconComponent: AlertCircle
  }
}

/**
 * AsyncError component - Standardized error display for async operations
 *
 * @param {Error|Object} error - Error object to display
 * @param {function} onRetry - Optional retry callback
 * @param {string} context - Context where error occurred (e.g., 'loading jobs')
 * @param {string} className - Additional CSS classes
 */
export default function AsyncError({
  error,
  onRetry,
  context = '',
  className = ''
}) {
  if (!error) return null

  const message = getErrorMessage(error)
  const network = isNetworkError(error)
  const server = isServerError(error)

  const variantKey = network ? 'network' : server ? 'server' : 'default'
  const styles = VARIANT_STYLES[variantKey]
  const Icon = styles.IconComponent

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      className={`${styles.container} rounded-xl p-4 border ${className}`}
    >
      <div className="flex items-start gap-3">
        <Icon className={`w-5 h-5 ${styles.icon} flex-shrink-0 mt-0.5`} />

        <div className="flex-1 min-w-0">
          {context && (
            <p className={`text-sm font-medium ${styles.title} mb-1`}>
              {context}
            </p>
          )}
          <p className={`text-sm ${styles.message}`}>
            {message}
          </p>
        </div>

        {onRetry && (
          <button
            onClick={onRetry}
            className={`flex-shrink-0 p-2 rounded-lg transition-colors ${styles.button}`}
            aria-label="Retry"
            title="Retry"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        )}
      </div>
    </motion.div>
  )
}

AsyncError.propTypes = {
  error: PropTypes.oneOfType([
    PropTypes.instanceOf(Error),
    PropTypes.object
  ]),
  onRetry: PropTypes.func,
  context: PropTypes.string,
  className: PropTypes.string
}
