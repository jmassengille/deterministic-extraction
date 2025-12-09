import clsx from 'clsx'
import PropTypes from 'prop-types'

const statusConfig = {
  pending: {
    color: 'bg-gray-100 text-gray-600 border-gray-200',
    label: 'Pending'
  },
  processing: {
    color: 'bg-blue-50 text-blue-600 border-blue-200',
    label: 'Processing'
  },
  completed: {
    color: 'bg-green-50 text-green-600 border-green-200',
    label: 'Completed'
  },
  failed: {
    color: 'bg-red-50 text-red-600 border-red-200',
    label: 'Failed'
  },
  cancelled: {
    color: 'bg-gray-100 text-gray-600 border-gray-200',
    label: 'Cancelled'
  }
}

export default function StatusBadge({ status, className }) {
  const config = statusConfig[status] || statusConfig.pending

  return (
    <span className={clsx(
      'px-2 py-1 text-xs font-medium rounded border',
      config.color,
      className
    )}>
      {config.label}
    </span>
  )
}

StatusBadge.propTypes = {
  status: PropTypes.oneOf(['pending', 'processing', 'completed', 'failed', 'cancelled']).isRequired,
  className: PropTypes.string
}