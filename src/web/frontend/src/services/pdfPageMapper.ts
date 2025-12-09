/**
 * PDF Page Mapper
 *
 * Maps MSF functions to PDF page numbers for auto-scroll functionality.
 *
 * Note: PDF page information is not stored in MSF files (MOX schema limitation).
 * These mappings must be maintained separately and can be:
 * - Auto-generated during extraction (from backend metadata)
 * - Manually set by user during editing
 * - Persisted to localStorage or backend
 *
 * Current implementation: In-memory storage only.
 * Future: Persist to localStorage with document path as key.
 */

/**
 * Function to PDF page mapping.
 */
export interface PageMapping {
  functionPUI: string
  pageNumber: number
  confidence?: number  // 0-1, if from auto-extraction
}

/**
 * Page mapping store (in-memory).
 * Key: functionPUI
 * Value: page number
 */
const pageMappings: Map<string, number> = new Map()

/**
 * Set page mapping for a function.
 *
 * @param functionPUI - Function UUID
 * @param pageNumber - PDF page number (1-indexed)
 */
export function setPageMapping(functionPUI: string, pageNumber: number): void {
  if (pageNumber < 1) {
    console.warn(`Invalid page number ${pageNumber}, must be >= 1`)
    return
  }
  if (!functionPUI || typeof functionPUI !== 'string') {
    console.warn('Invalid functionPUI provided')
    return
  }
  pageMappings.set(functionPUI, pageNumber)
}

/**
 * Get page mapping for a function.
 *
 * @param functionPUI - Function UUID
 * @returns Page number or null if not mapped
 */
export function getPageMapping(functionPUI: string): number | null {
  return pageMappings.get(functionPUI) || null
}

/**
 * Remove page mapping for a function.
 *
 * @param functionPUI - Function UUID
 */
export function removePageMapping(functionPUI: string): void {
  pageMappings.delete(functionPUI)
}

/**
 * Clear all page mappings.
 * Useful when switching documents.
 */
export function clearAllPageMappings(): void {
  pageMappings.clear()
}

/**
 * Get all page mappings.
 *
 * @returns Array of page mappings
 */
export function getAllPageMappings(): PageMapping[] {
  const mappings: PageMapping[] = []
  pageMappings.forEach((pageNumber, functionPUI) => {
    mappings.push({ functionPUI, pageNumber })
  })
  return mappings
}

/**
 * Bulk load page mappings from extraction metadata.
 *
 * @param mappings - Array of page mappings
 */
export function loadPageMappings(mappings: PageMapping[]): void {
  clearAllPageMappings()
  mappings.forEach(({ functionPUI, pageNumber }) => {
    setPageMapping(functionPUI, pageNumber)
  })
}

/**
 * Estimate page number for a function based on sequence.
 * Fallback when no explicit mapping exists.
 *
 * Used for:
 * - Manually created MSF files (no extraction metadata)
 * - Functions added by user
 *
 * Strategy:
 * - First function → page 1
 * - Subsequent functions → page 1 + (sequence * estimated_pages_per_function)
 * - Default estimate: 3 pages per function (spec tables are typically 2-5 pages)
 *
 * @param sequence - Function sequence number (0-indexed)
 * @param totalFunctions - Total number of functions in document
 * @param totalPages - Total pages in PDF (optional)
 * @returns Estimated page number
 */
export function estimatePageNumber(
  sequence: number,
  totalFunctions: number,
  totalPages?: number
): number {
  if (sequence === 0) return 1

  // If we know total pages, distribute evenly
  if (totalPages) {
    const pagesPerFunction = Math.floor(totalPages / totalFunctions)
    return Math.max(1, 1 + sequence * pagesPerFunction)
  }

  // Otherwise use default estimate
  const defaultPagesPerFunction = 3
  return 1 + sequence * defaultPagesPerFunction
}

/**
 * Persist mappings to localStorage.
 *
 * @param documentPath - Document path (used as key)
 * @param mappings - Page mappings to persist
 */
export function persistMappings(documentPath: string, mappings: PageMapping[]): void {
  const key = `pdf_page_mappings:${documentPath}`
  localStorage.setItem(key, JSON.stringify(mappings))
}

/**
 * Load mappings from localStorage.
 *
 * @param documentPath - Document path (used as key)
 * @returns Loaded mappings or empty array if none found
 */
export function loadPersistedMappings(documentPath: string): PageMapping[] {
  const key = `pdf_page_mappings:${documentPath}`
  const data = localStorage.getItem(key)
  if (!data) return []

  try {
    return JSON.parse(data)
  } catch (e) {
    console.error('Failed to parse persisted page mappings:', e)
    return []
  }
}

/**
 * Clear persisted mappings for a document.
 *
 * @param documentPath - Document path (used as key)
 */
export function clearPersistedMappings(documentPath: string): void {
  const key = `pdf_page_mappings:${documentPath}`
  localStorage.removeItem(key)
}
