/**
 * MSF Store Tests
 *
 * Tests Zustand store for MSF document state management.
 * Validates document loading, selection, mutations, and selectors.
 */

import { describe, it, expect, beforeEach } from 'vitest'
import {
  useMSFStore,
  useSelectedFunction,
  useSelectedRange,
  useSelectedSpecification,
  useFunctions,
  useIsDirty,
  useSelection
} from '../../store/msfStore'
import type {
  MSFDocumentNormalized,
  MSFFunctionNormalized,
  MSFRangeNormalized
} from '../../types/msf.types'

// Helper to create minimal test document
function createTestDocument(): MSFDocumentNormalized {
  return {
    instrument: {
      pui: '{TEST-INST-PUI}',
      dui: '{TEST-INST-DUI}',
      verified: true,
      review: false,
      filenotes: '',
      filehistory: '',
      header: {
        pui: '{TEST-HEADER-PUI}',
        dui: '{TEST-HEADER-DUI}',
        model: 'Test Model',
        manufacturer: 'Test Mfg',
        description: 'Test Description',
        confidence: 0,
        confidenceDesc: '',
        specreference: '',
        author: '',
        verifiedby: '',
        approvedby: '',
        approvedate: '',
        save_date: '',
        saved_by: '',
        revision: 0,
        app_name: '',
        app_version: '',
        source_filename: '',
        source_date: '',
        lims_widgetcode: 0,
        lims_equipclass: 0,
        noteidlist: '',
        isactive: false,
        verified: false,
        review: false,
        revisionnotes: ''
      },
      functions: [
        {
          pui: '{FUNC1-PUI}',
          dui: '{FUNC1-DUI}',
          sequence: 0,
          functionname: 'Test Function 1',
          modifier: null,
          properties: '',
          format: '',
          isoutput: false,
          noteidlist: '',
          verified: false,
          review: false,
          ranges: [
            {
              pui: '{RANGE1-PUI}',
              dui: '{RANGE1-DUI}',
              sequence: 0,
              rangename: 'Test Range 1',
              rangeid: '',
              properties: '',
              autoassign: false,
              noteidlist: '',
              verified: false,
              review: false,
              parameter: {
                pui: '{PARAM1-PUI}',
                dui: '{PARAM1-DUI}',
                sequence: 0,
                lowerlimit: 0,
                upperlimit: 100,
                unitofmeasure: 'volt',
                unitsymbol: 'V',
                isbipolar: false,
                noteidlist: '',
                paramname: '',
                verified: false,
                review: false
              },
              specifications: [
                {
                  pui: '{SPEC1-PUI}',
                  dui: '{SPEC1-DUI}',
                  sequence: 0,
                  calinterval: 365,
                  Specialcal: '',
                  AssetNum: '',
                  spectype: 'Accuracy',
                  unitofmeasure: 'volt',
                  unitsymbol: 'V',
                  fullscale: 0,
                  iv_pct: 0.1,
                  iv_pct_hi: 0,
                  iv_ppm: 0,
                  fs_pct: 0,
                  fs_pct_hi: 0,
                  fs_ppm: 0,
                  floor: 0,
                  floor_hi: 0,
                  db: 0,
                  dbtype: 0,
                  calcdesc: '',
                  calcstring: '',
                  operand: ''
                }
              ]
            }
          ],
          _uiExpanded: false,
          _uiStatus: 'unreviewed'
        }
      ]
    }
  }
}

describe('MSF Store', () => {
  beforeEach(() => {
    // Reset store before each test
    useMSFStore.getState().clearDocument()
  })

  describe('loadDocument', () => {
    it('loads document and sets path', () => {
      const doc = createTestDocument()
      const store = useMSFStore.getState()

      store.loadDocument(doc, 'test.msf')

      const state = useMSFStore.getState()
      expect(state.document).toBe(doc)
      expect(state.documentPath).toBe('test.msf')
      expect(state.isDirty).toBe(false)
    })

    it('clears selection on load', () => {
      const doc = createTestDocument()
      const store = useMSFStore.getState()

      // First load and select something
      store.loadDocument(doc, 'test.msf')
      store.selectFunction('{FUNC1-PUI}')

      // Load different document
      store.loadDocument(createTestDocument(), 'test2.msf')

      const state = useMSFStore.getState()
      expect(state.selection.type).toBe(null)
      expect(state.selection.functionPUI).toBe(null)
    })
  })

  describe('clearDocument', () => {
    it('clears all state', () => {
      const doc = createTestDocument()
      const store = useMSFStore.getState()

      store.loadDocument(doc, 'test.msf')
      store.selectFunction('{FUNC1-PUI}')
      store.clearDocument()

      const state = useMSFStore.getState()
      expect(state.document).toBe(null)
      expect(state.documentPath).toBe(null)
      expect(state.isDirty).toBe(false)
      expect(state.selection.type).toBe(null)
    })
  })

  describe('Selection', () => {
    beforeEach(() => {
      const doc = createTestDocument()
      useMSFStore.getState().loadDocument(doc, 'test.msf')
    })

    it('selects function', () => {
      const store = useMSFStore.getState()
      store.selectFunction('{FUNC1-PUI}')

      const state = useMSFStore.getState()
      expect(state.selection.type).toBe('function')
      expect(state.selection.functionPUI).toBe('{FUNC1-PUI}')
      expect(state.selection.rangePUI).toBe(null)
      expect(state.selection.specificationPUI).toBe(null)
    })

    it('selects range', () => {
      const store = useMSFStore.getState()
      store.selectRange('{FUNC1-PUI}', '{RANGE1-PUI}')

      const state = useMSFStore.getState()
      expect(state.selection.type).toBe('range')
      expect(state.selection.functionPUI).toBe('{FUNC1-PUI}')
      expect(state.selection.rangePUI).toBe('{RANGE1-PUI}')
      expect(state.selection.specificationPUI).toBe(null)
    })

    it('selects specification', () => {
      const store = useMSFStore.getState()
      store.selectSpecification('{FUNC1-PUI}', '{RANGE1-PUI}', '{SPEC1-PUI}')

      const state = useMSFStore.getState()
      expect(state.selection.type).toBe('specification')
      expect(state.selection.functionPUI).toBe('{FUNC1-PUI}')
      expect(state.selection.rangePUI).toBe('{RANGE1-PUI}')
      expect(state.selection.specificationPUI).toBe('{SPEC1-PUI}')
    })

    it('clears selection', () => {
      const store = useMSFStore.getState()
      store.selectFunction('{FUNC1-PUI}')
      store.clearSelection()

      const state = useMSFStore.getState()
      expect(state.selection.type).toBe(null)
      expect(state.selection.functionPUI).toBe(null)
    })
  })

  describe('Mutations', () => {
    beforeEach(() => {
      const doc = createTestDocument()
      useMSFStore.getState().loadDocument(doc, 'test.msf')
    })

    it('updates function', () => {
      const store = useMSFStore.getState()
      store.updateFunction('{FUNC1-PUI}', { functionname: 'Updated Name' })

      const state = useMSFStore.getState()
      expect(state.document?.instrument.functions[0].functionname).toBe('Updated Name')
      expect(state.isDirty).toBe(true)
    })

    it('updates range', () => {
      const store = useMSFStore.getState()
      store.updateRange('{FUNC1-PUI}', '{RANGE1-PUI}', { rangename: 'Updated Range' })

      const state = useMSFStore.getState()
      expect(state.document?.instrument.functions[0].ranges[0].rangename).toBe('Updated Range')
      expect(state.isDirty).toBe(true)
    })

    it('updates specification', () => {
      const store = useMSFStore.getState()
      store.updateSpecification('{FUNC1-PUI}', '{RANGE1-PUI}', '{SPEC1-PUI}', { iv_pct: 0.5 })

      const state = useMSFStore.getState()
      expect(
        state.document?.instrument.functions[0].ranges[0].specifications[0].iv_pct
      ).toBe(0.5)
      expect(state.isDirty).toBe(true)
    })

    it('does not mutate when document is null', () => {
      const store = useMSFStore.getState()
      store.clearDocument()
      store.updateFunction('{FUNC1-PUI}', { functionname: 'Should Not Update' })

      const state = useMSFStore.getState()
      expect(state.document).toBe(null)
      expect(state.isDirty).toBe(false)
    })
  })

  describe('Add/Delete', () => {
    beforeEach(() => {
      const doc = createTestDocument()
      useMSFStore.getState().loadDocument(doc, 'test.msf')
    })

    it('adds function', () => {
      const store = useMSFStore.getState()
      const newFunc: MSFFunctionNormalized = {
        pui: '{FUNC2-PUI}',
        dui: '{FUNC2-DUI}',
        sequence: 1,
        functionname: 'New Function',
        modifier: null,
        properties: '',
        format: '',
        isoutput: false,
        noteidlist: '',
        verified: false,
        review: false,
        ranges: [],
        _uiExpanded: false,
        _uiStatus: 'unreviewed'
      }

      store.addFunction(newFunc)

      const state = useMSFStore.getState()
      expect(state.document?.instrument.functions.length).toBe(2)
      expect(state.document?.instrument.functions[1].pui).toBe('{FUNC2-PUI}')
      expect(state.isDirty).toBe(true)
    })

    it('deletes function', () => {
      const store = useMSFStore.getState()
      store.deleteFunction('{FUNC1-PUI}')

      const state = useMSFStore.getState()
      expect(state.document?.instrument.functions.length).toBe(0)
      expect(state.isDirty).toBe(true)
    })

    it('clears selection when deleting selected function', () => {
      const store = useMSFStore.getState()
      store.selectFunction('{FUNC1-PUI}')
      store.deleteFunction('{FUNC1-PUI}')

      const state = useMSFStore.getState()
      expect(state.selection.type).toBe(null)
      expect(state.selection.functionPUI).toBe(null)
    })
  })

  describe('markClean', () => {
    it('clears dirty flag', () => {
      const doc = createTestDocument()
      const store = useMSFStore.getState()

      store.loadDocument(doc, 'test.msf')
      store.updateFunction('{FUNC1-PUI}', { functionname: 'Changed' })

      expect(useMSFStore.getState().isDirty).toBe(true)

      store.markClean()

      expect(useMSFStore.getState().isDirty).toBe(false)
    })
  })

  describe('State queries', () => {
    beforeEach(() => {
      const doc = createTestDocument()
      useMSFStore.getState().loadDocument(doc, 'test.msf')
    })

    it('retrieves selected function from state', () => {
      const store = useMSFStore.getState()
      store.selectFunction('{FUNC1-PUI}')

      const state = useMSFStore.getState()
      const func = state.document?.instrument.functions.find(
        f => f.pui === state.selection.functionPUI
      )
      expect(func?.pui).toBe('{FUNC1-PUI}')
      expect(func?.functionname).toBe('Test Function 1')
    })

    it('retrieves selected range from state', () => {
      const store = useMSFStore.getState()
      store.selectRange('{FUNC1-PUI}', '{RANGE1-PUI}')

      const state = useMSFStore.getState()
      const func = state.document?.instrument.functions.find(
        f => f.pui === state.selection.functionPUI
      )
      const range = func?.ranges.find(r => r.pui === state.selection.rangePUI)
      expect(range?.pui).toBe('{RANGE1-PUI}')
      expect(range?.rangename).toBe('Test Range 1')
    })

    it('retrieves selected specification from state', () => {
      const store = useMSFStore.getState()
      store.selectSpecification('{FUNC1-PUI}', '{RANGE1-PUI}', '{SPEC1-PUI}')

      const state = useMSFStore.getState()
      const func = state.document?.instrument.functions.find(
        f => f.pui === state.selection.functionPUI
      )
      const range = func?.ranges.find(r => r.pui === state.selection.rangePUI)
      const spec = range?.specifications.find(
        s => s.pui === state.selection.specificationPUI
      )
      expect(spec?.pui).toBe('{SPEC1-PUI}')
      expect(spec?.spectype).toBe('Accuracy')
    })

    it('retrieves all functions from state', () => {
      const state = useMSFStore.getState()
      const funcs = state.document?.instrument.functions || []
      expect(funcs.length).toBe(1)
      expect(funcs[0].pui).toBe('{FUNC1-PUI}')
    })

    it('retrieves dirty flag from state', () => {
      let state = useMSFStore.getState()
      expect(state.isDirty).toBe(false)

      useMSFStore.getState().updateFunction('{FUNC1-PUI}', { functionname: 'Changed' })

      state = useMSFStore.getState()
      expect(state.isDirty).toBe(true)
    })

    it('retrieves selection state', () => {
      useMSFStore.getState().selectFunction('{FUNC1-PUI}')

      const state = useMSFStore.getState()
      expect(state.selection.type).toBe('function')
      expect(state.selection.functionPUI).toBe('{FUNC1-PUI}')
    })

    it('returns null when nothing selected', () => {
      const state = useMSFStore.getState()
      expect(state.selection.type).toBe(null)
      expect(state.selection.functionPUI).toBe(null)
      expect(state.selection.rangePUI).toBe(null)
      expect(state.selection.specificationPUI).toBe(null)
    })
  })
})
