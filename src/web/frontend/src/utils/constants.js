// Job status constants
export const JOB_STATUS = {
  PENDING: 'pending',
  PROCESSING: 'processing',
  COMPLETED: 'completed',
  FAILED: 'failed',
  CANCELLED: 'cancelled'
}

// Job stages for progress tracking
export const JOB_STAGES = {
  QUEUED: 'queued',
  LOADING_DOCUMENT: 'loading_document',
  ANALYZING_STRUCTURE: 'analyzing_structure',
  EXTRACTING_REGIONS: 'extracting_regions',
  PROCESSING_DATA: 'processing_data',
  GENERATING_OUTPUT: 'generating_output',
  FINALIZING: 'finalizing'
}

// Stage display names
export const STAGE_LABELS = {
  [JOB_STAGES.QUEUED]: 'Queued',
  [JOB_STAGES.LOADING_DOCUMENT]: 'Loading Document',
  [JOB_STAGES.ANALYZING_STRUCTURE]: 'Analyzing Structure',
  [JOB_STAGES.EXTRACTING_REGIONS]: 'Extracting Regions',
  [JOB_STAGES.PROCESSING_DATA]: 'Processing Data',
  [JOB_STAGES.GENERATING_OUTPUT]: 'Generating Output',
  [JOB_STAGES.FINALIZING]: 'Finalizing'
}

// File size limits
export const FILE_LIMITS = {
  MAX_SIZE_MB: 100,
  MAX_SIZE_BYTES: 100 * 1024 * 1024,
  ALLOWED_TYPES: ['application/pdf']
}

// Polling intervals
export const POLLING_INTERVALS = {
  HEALTH_CHECK: 30000, // 30 seconds
  JOB_LIST: 5000, // 5 seconds
  PROGRESS_RETRY: 2000 // 2 seconds
}