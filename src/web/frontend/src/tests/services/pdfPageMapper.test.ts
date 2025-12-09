/**
 * PDF Page Mapper Tests
 *
 * Tests function-to-PDF-page mapping functionality.
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import {
  setPageMapping,
  getPageMapping,
  removePageMapping,
  clearAllPageMappings,
  getAllPageMappings,
  loadPageMappings,
  estimatePageNumber,
  persistMappings,
  loadPersistedMappings,
  clearPersistedMappings
} from '../../services/pdfPageMapper'

describe('PDF Page Mapper', () => {
  beforeEach(() => {
    clearAllPageMappings()
    localStorage.clear()
  })

  afterEach(() => {
    clearAllPageMappings()
    localStorage.clear()
  })

  describe('setPageMapping / getPageMapping', () => {
    it('sets and retrieves page mapping', () => {
      setPageMapping('{FUNC-1}', 5)
      expect(getPageMapping('{FUNC-1}')).toBe(5)
    })

    it('returns null for unmapped function', () => {
      expect(getPageMapping('{NONEXISTENT}')).toBe(null)
    })

    it('overwrites existing mapping', () => {
      setPageMapping('{FUNC-1}', 5)
      setPageMapping('{FUNC-1}', 10)
      expect(getPageMapping('{FUNC-1}')).toBe(10)
    })

    it('rejects invalid page numbers', () => {
      setPageMapping('{FUNC-1}', 0)
      expect(getPageMapping('{FUNC-1}')).toBe(null)

      setPageMapping('{FUNC-1}', -5)
      expect(getPageMapping('{FUNC-1}')).toBe(null)
    })
  })

  describe('removePageMapping', () => {
    it('removes page mapping', () => {
      setPageMapping('{FUNC-1}', 5)
      removePageMapping('{FUNC-1}')
      expect(getPageMapping('{FUNC-1}')).toBe(null)
    })

    it('does not throw when removing nonexistent mapping', () => {
      expect(() => removePageMapping('{NONEXISTENT}')).not.toThrow()
    })
  })

  describe('clearAllPageMappings', () => {
    it('clears all mappings', () => {
      setPageMapping('{FUNC-1}', 5)
      setPageMapping('{FUNC-2}', 10)
      setPageMapping('{FUNC-3}', 15)

      clearAllPageMappings()

      expect(getPageMapping('{FUNC-1}')).toBe(null)
      expect(getPageMapping('{FUNC-2}')).toBe(null)
      expect(getPageMapping('{FUNC-3}')).toBe(null)
    })
  })

  describe('getAllPageMappings', () => {
    it('returns empty array when no mappings', () => {
      expect(getAllPageMappings()).toEqual([])
    })

    it('returns all mappings', () => {
      setPageMapping('{FUNC-1}', 5)
      setPageMapping('{FUNC-2}', 10)

      const mappings = getAllPageMappings()

      expect(mappings).toHaveLength(2)
      expect(mappings).toContainEqual({ functionPUI: '{FUNC-1}', pageNumber: 5 })
      expect(mappings).toContainEqual({ functionPUI: '{FUNC-2}', pageNumber: 10 })
    })
  })

  describe('loadPageMappings', () => {
    it('loads mappings in bulk', () => {
      const mappings = [
        { functionPUI: '{FUNC-1}', pageNumber: 5 },
        { functionPUI: '{FUNC-2}', pageNumber: 10 },
        { functionPUI: '{FUNC-3}', pageNumber: 15 }
      ]

      loadPageMappings(mappings)

      expect(getPageMapping('{FUNC-1}')).toBe(5)
      expect(getPageMapping('{FUNC-2}')).toBe(10)
      expect(getPageMapping('{FUNC-3}')).toBe(15)
    })

    it('clears existing mappings before loading', () => {
      setPageMapping('{FUNC-OLD}', 99)

      const mappings = [
        { functionPUI: '{FUNC-1}', pageNumber: 5 }
      ]

      loadPageMappings(mappings)

      expect(getPageMapping('{FUNC-OLD}')).toBe(null)
      expect(getPageMapping('{FUNC-1}')).toBe(5)
    })
  })

  describe('estimatePageNumber', () => {
    it('returns page 1 for first function', () => {
      expect(estimatePageNumber(0, 5)).toBe(1)
    })

    it('estimates based on default pages per function', () => {
      // Default: 3 pages per function
      expect(estimatePageNumber(1, 5)).toBe(4)  // 1 + 1*3
      expect(estimatePageNumber(2, 5)).toBe(7)  // 1 + 2*3
      expect(estimatePageNumber(3, 5)).toBe(10) // 1 + 3*3
    })

    it('distributes evenly when total pages known', () => {
      const totalFunctions = 5
      const totalPages = 50

      // 50 pages / 5 functions = 10 pages per function
      expect(estimatePageNumber(0, totalFunctions, totalPages)).toBe(1)
      expect(estimatePageNumber(1, totalFunctions, totalPages)).toBe(11) // 1 + 1*10
      expect(estimatePageNumber(2, totalFunctions, totalPages)).toBe(21) // 1 + 2*10
    })

    it('returns at least page 1', () => {
      expect(estimatePageNumber(0, 1, 100)).toBe(1)
      expect(estimatePageNumber(0, 100, 1)).toBe(1)
    })
  })

  describe('Persistence', () => {
    const docPath = 'test-document.msf'

    it('persists and loads mappings', () => {
      const mappings = [
        { functionPUI: '{FUNC-1}', pageNumber: 5 },
        { functionPUI: '{FUNC-2}', pageNumber: 10 }
      ]

      persistMappings(docPath, mappings)
      const loaded = loadPersistedMappings(docPath)

      expect(loaded).toEqual(mappings)
    })

    it('returns empty array when no persisted mappings', () => {
      const loaded = loadPersistedMappings('nonexistent.msf')
      expect(loaded).toEqual([])
    })

    it('clears persisted mappings', () => {
      const mappings = [
        { functionPUI: '{FUNC-1}', pageNumber: 5 }
      ]

      persistMappings(docPath, mappings)
      clearPersistedMappings(docPath)

      const loaded = loadPersistedMappings(docPath)
      expect(loaded).toEqual([])
    })

    it('handles corrupted localStorage data', () => {
      const key = `pdf_page_mappings:${docPath}`
      localStorage.setItem(key, 'invalid json {{{')

      const loaded = loadPersistedMappings(docPath)
      expect(loaded).toEqual([])
    })

    it('stores separate mappings per document', () => {
      const mappings1 = [{ functionPUI: '{FUNC-1}', pageNumber: 5 }]
      const mappings2 = [{ functionPUI: '{FUNC-2}', pageNumber: 10 }]

      persistMappings('doc1.msf', mappings1)
      persistMappings('doc2.msf', mappings2)

      expect(loadPersistedMappings('doc1.msf')).toEqual(mappings1)
      expect(loadPersistedMappings('doc2.msf')).toEqual(mappings2)
    })
  })
})
