/**
 * Error handling utilities for consistent error messaging and classification
 */

/**
 * Extract user-friendly error message from various error types
 *
 * @param {Error|Object} error - Error object from API or network
 * @returns {string} User-friendly error message
 */
export function getErrorMessage(error) {
  if (!error) {
    return 'An unknown error occurred'
  }

  // Network errors (no response from server)
  if (!error.response && error.request) {
    return 'Unable to connect to server. Please check your connection.'
  }

  // API error with response
  if (error.response) {
    const { data, status } = error.response

    // FastAPI validation errors
    if (data?.detail && Array.isArray(data.detail)) {
      return data.detail.map(err => err.msg).join(', ')
    }

    // FastAPI simple detail message
    if (data?.detail && typeof data.detail === 'string') {
      return data.detail
    }

    // Generic error message
    if (data?.message) {
      return data.message
    }

    // Status-based messages
    switch (status) {
      case 400:
        return 'Invalid request. Please check your input.'
      case 401:
        return 'Unauthorized. Please log in again.'
      case 403:
        return 'You do not have permission to perform this action.'
      case 404:
        return 'Resource not found.'
      case 409:
        return 'This action conflicts with existing data.'
      case 413:
        return 'File is too large to upload.'
      case 422:
        return 'Invalid data format. Please check your input.'
      case 429:
        return 'Too many requests. Please wait a moment and try again.'
      case 500:
        return 'Server error. Please try again later.'
      case 503:
        return 'Service temporarily unavailable. Please try again later.'
      default:
        return `Request failed with status ${status}`
    }
  }

  // JavaScript Error object
  if (error.message) {
    return error.message
  }

  // String error
  if (typeof error === 'string') {
    return error
  }

  return 'An unexpected error occurred'
}

/**
 * Check if error is a network error (server unreachable)
 *
 * @param {Error|Object} error - Error object
 * @returns {boolean} True if network error
 */
export function isNetworkError(error) {
  return !error.response && error.request
}

/**
 * Check if error is a validation error (400/422)
 *
 * @param {Error|Object} error - Error object
 * @returns {boolean} True if validation error
 */
export function isValidationError(error) {
  const status = error.response?.status
  return status === 400 || status === 422
}

/**
 * Check if error is an authentication error (401)
 *
 * @param {Error|Object} error - Error object
 * @returns {boolean} True if auth error
 */
export function isAuthError(error) {
  return error.response?.status === 401
}

/**
 * Check if error is a server error (5xx)
 *
 * @param {Error|Object} error - Error object
 * @returns {boolean} True if server error
 */
export function isServerError(error) {
  const status = error.response?.status
  return status >= 500 && status < 600
}

/**
 * Determine if error is retryable
 *
 * @param {Error|Object} error - Error object
 * @returns {boolean} True if operation can be retried
 */
export function isRetryableError(error) {
  if (isNetworkError(error)) {
    return true
  }

  const status = error.response?.status
  return status === 408 || status === 429 || status === 503 || status >= 500
}

/**
 * Get error severity level for logging/monitoring
 *
 * @param {Error|Object} error - Error object
 * @returns {'low'|'medium'|'high'|'critical'} Severity level
 */
export function getErrorSeverity(error) {
  if (isAuthError(error)) {
    return 'medium'
  }

  if (isValidationError(error)) {
    return 'low'
  }

  if (isNetworkError(error)) {
    return 'high'
  }

  if (isServerError(error)) {
    return 'critical'
  }

  const status = error.response?.status
  if (status === 403) {
    return 'medium'
  }

  if (status === 404) {
    return 'low'
  }

  return 'medium'
}

/**
 * Format error for display in UI
 *
 * @param {Error|Object} error - Error object
 * @param {string} context - Context where error occurred (e.g., 'uploading file')
 * @returns {Object} Formatted error info
 */
export function formatErrorForDisplay(error, context = '') {
  const message = getErrorMessage(error)
  const severity = getErrorSeverity(error)
  const retryable = isRetryableError(error)

  return {
    message: context ? `Error ${context}: ${message}` : message,
    severity,
    retryable,
    details: error.response?.data || null
  }
}
