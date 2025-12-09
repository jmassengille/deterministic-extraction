/**
 * Template Extractor Tests
 *
 * Tests function template extraction and instantiation.
 */

import { describe, it, expect } from 'vitest'
import {
  extractFunctionTemplate,
  createFunctionFromTemplate,
  getAvailableTemplates,
  getTemplate,
  PREDEFINED_TEMPLATES
} from '../../services/templateExtractor'
import type { MSFFunctionNormalized } from '../../types/msf.types'
import { isValidMOXUUID } from '../../services/uuidGenerator'

// Helper to create test function
function createTestFunction(): MSFFunctionNormalized {
  return {
    pui: '{FUNC-PUI}',
    dui: '{FUNC-DUI}',
    sequence: 0,
    functionname: 'Test Function',
    modifier: null,
    properties: '',
    format: '',
    isoutput: false,
    noteidlist: '',
    verified: false,
    review: false,
    ranges: [
      {
        pui: '{RANGE-PUI}',
        dui: '{RANGE-DUI}',
        sequence: 0,
        rangename: 'Test Range',
        rangeid: '',
        properties: '',
        autoassign: true,
        noteidlist: '',
        verified: false,
        review: false,
        parameter: {
          pui: '{PARAM-PUI}',
          dui: '{PARAM-DUI}',
          sequence: 0,
          lowerlimit: 0,
          upperlimit: 100,
          unitofmeasure: 'volt',
          unitsymbol: 'V',
          isbipolar: true,
          noteidlist: '',
          paramname: '',
          verified: false,
          review: false
        },
        specifications: [
          {
            pui: '{SPEC-PUI}',
            dui: '{SPEC-DUI}',
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
            operand: 'PlusMinus'
          }
        ]
      }
    ],
    _uiExpanded: false,
    _uiStatus: 'unreviewed'
  }
}

describe('extractFunctionTemplate', () => {
  it('extracts template from function', () => {
    const func = createTestFunction()
    const template = extractFunctionTemplate(func)

    expect(template.functionname).toBe('Test Function')
    expect(template.isoutput).toBe(false)
    expect(template.ranges).toHaveLength(1)
  })

  it('strips UUIDs from template', () => {
    const func = createTestFunction()
    const template = extractFunctionTemplate(func)

    // Template should not have UUIDs
    expect(template).not.toHaveProperty('pui')
    expect(template).not.toHaveProperty('dui')
    expect(template.ranges[0]).not.toHaveProperty('pui')
    expect(template.ranges[0]).not.toHaveProperty('dui')
  })

  it('strips metadata fields from template', () => {
    const func = createTestFunction()
    const template = extractFunctionTemplate(func)

    expect(template).not.toHaveProperty('verified')
    expect(template).not.toHaveProperty('review')
    expect(template).not.toHaveProperty('noteidlist')
    expect(template).not.toHaveProperty('_uiExpanded')
  })

  it('preserves data fields in template', () => {
    const func = createTestFunction()
    func.functionname = 'Custom Name'
    func.modifier = 'RMS'
    func.ranges[0].rangename = 'Custom Range'
    func.ranges[0].parameter.unitofmeasure = 'ampere'

    const template = extractFunctionTemplate(func)

    expect(template.functionname).toBe('Custom Name')
    expect(template.modifier).toBe('RMS')
    expect(template.ranges[0].rangename).toBe('Custom Range')
    expect(template.ranges[0].parameter.unitofmeasure).toBe('ampere')
  })
})

describe('createFunctionFromTemplate', () => {
  it('creates function from template', () => {
    const func = createTestFunction()
    const template = extractFunctionTemplate(func)
    const newFunc = createFunctionFromTemplate(template, 5)

    expect(newFunc.functionname).toBe('Test Function')
    expect(newFunc.sequence).toBe(5)
    expect(newFunc.ranges).toHaveLength(1)
  })

  it('generates fresh UUIDs for all entities', () => {
    const func = createTestFunction()
    const template = extractFunctionTemplate(func)
    const newFunc = createFunctionFromTemplate(template, 0)

    // All UUIDs should be valid MOX format
    expect(isValidMOXUUID(newFunc.pui)).toBe(true)
    expect(isValidMOXUUID(newFunc.dui)).toBe(true)
    expect(isValidMOXUUID(newFunc.ranges[0].pui)).toBe(true)
    expect(isValidMOXUUID(newFunc.ranges[0].dui)).toBe(true)
    expect(isValidMOXUUID(newFunc.ranges[0].parameter.pui)).toBe(true)
    expect(isValidMOXUUID(newFunc.ranges[0].parameter.dui)).toBe(true)
    expect(isValidMOXUUID(newFunc.ranges[0].specifications[0].pui)).toBe(true)
    expect(isValidMOXUUID(newFunc.ranges[0].specifications[0].dui)).toBe(true)
  })

  it('generates unique UUIDs (not same as original)', () => {
    const func = createTestFunction()
    const template = extractFunctionTemplate(func)
    const newFunc = createFunctionFromTemplate(template, 0)

    expect(newFunc.pui).not.toBe(func.pui)
    expect(newFunc.dui).not.toBe(func.dui)
    expect(newFunc.ranges[0].pui).not.toBe(func.ranges[0].pui)
  })

  it('generates unique UUIDs between multiple instances', () => {
    const func = createTestFunction()
    const template = extractFunctionTemplate(func)
    const func1 = createFunctionFromTemplate(template, 0)
    const func2 = createFunctionFromTemplate(template, 1)

    expect(func1.pui).not.toBe(func2.pui)
    expect(func1.dui).not.toBe(func2.dui)
    expect(func1.ranges[0].pui).not.toBe(func2.ranges[0].pui)
  })

  it('initializes metadata fields correctly', () => {
    const func = createTestFunction()
    const template = extractFunctionTemplate(func)
    const newFunc = createFunctionFromTemplate(template, 0)

    expect(newFunc.verified).toBe(false)
    expect(newFunc.review).toBe(false)
    expect(newFunc.noteidlist).toBe('')
    expect(newFunc._uiExpanded).toBe(false)
    expect(newFunc._uiStatus).toBe('unreviewed')
  })

  it('handles modifier correctly', () => {
    const func = createTestFunction()
    func.modifier = 'Peak'
    const template = extractFunctionTemplate(func)
    const newFunc = createFunctionFromTemplate(template, 0)

    expect(newFunc.modifier).toBe('Peak')
  })
})

describe('Pre-defined templates', () => {
  it('has voltage-dc template', () => {
    const template = PREDEFINED_TEMPLATES['voltage-dc']
    expect(template).toBeDefined()
    expect(template.functionname).toBe('Voltage, DC')
    expect(template.ranges).toHaveLength(1)
    expect(template.ranges[0].parameter.unitofmeasure).toBe('volt')
  })

  it('has voltage-ac template', () => {
    const template = PREDEFINED_TEMPLATES['voltage-ac']
    expect(template).toBeDefined()
    expect(template.functionname).toBe('Voltage, AC')
  })

  it('has resistance template', () => {
    const template = PREDEFINED_TEMPLATES['resistance']
    expect(template).toBeDefined()
    expect(template.functionname).toBe('Resistance')
    expect(template.ranges[0].parameter.unitofmeasure).toBe('ohm')
  })

  it('has current-dc template', () => {
    const template = PREDEFINED_TEMPLATES['current-dc']
    expect(template).toBeDefined()
    expect(template.functionname).toBe('Current, DC')
    expect(template.ranges[0].parameter.unitofmeasure).toBe('ampere')
  })

  it('all templates have valid structure', () => {
    Object.values(PREDEFINED_TEMPLATES).forEach(template => {
      expect(template.functionname).toBeTruthy()
      expect(template.ranges).toBeInstanceOf(Array)
      expect(template.ranges.length).toBeGreaterThan(0)
      expect(template.ranges[0].parameter).toBeDefined()
      expect(template.ranges[0].specifications).toBeInstanceOf(Array)
      expect(template.ranges[0].specifications.length).toBeGreaterThan(0)
    })
  })

  it('all templates can be instantiated', () => {
    Object.values(PREDEFINED_TEMPLATES).forEach(template => {
      const func = createFunctionFromTemplate(template, 0)
      expect(func).toBeDefined()
      expect(isValidMOXUUID(func.pui)).toBe(true)
      expect(isValidMOXUUID(func.dui)).toBe(true)
    })
  })
})

describe('getAvailableTemplates', () => {
  it('returns list of template keys', () => {
    const keys = getAvailableTemplates()
    expect(keys).toBeInstanceOf(Array)
    expect(keys.length).toBeGreaterThan(0)
    expect(keys).toContain('voltage-dc')
    expect(keys).toContain('voltage-ac')
    expect(keys).toContain('resistance')
    expect(keys).toContain('current-dc')
  })
})

describe('getTemplate', () => {
  it('returns template by key', () => {
    const template = getTemplate('voltage-dc')
    expect(template).toBeDefined()
    expect(template?.functionname).toBe('Voltage, DC')
  })

  it('returns null for invalid key', () => {
    const template = getTemplate('nonexistent')
    expect(template).toBe(null)
  })
})

describe('Roundtrip template extraction and instantiation', () => {
  it('preserves data through extract and create cycle', () => {
    const original = createTestFunction()
    original.functionname = 'Custom Function'
    original.modifier = 'RMS'
    original.ranges[0].rangename = 'Custom Range'
    original.ranges[0].parameter.lowerlimit = 10
    original.ranges[0].parameter.upperlimit = 500

    // Extract template
    const template = extractFunctionTemplate(original)

    // Create new function
    const newFunc = createFunctionFromTemplate(template, 7)

    // Data should be preserved
    expect(newFunc.functionname).toBe('Custom Function')
    expect(newFunc.modifier).toBe('RMS')
    expect(newFunc.ranges[0].rangename).toBe('Custom Range')
    expect(newFunc.ranges[0].parameter.lowerlimit).toBe(10)
    expect(newFunc.ranges[0].parameter.upperlimit).toBe(500)

    // Sequence should be new value
    expect(newFunc.sequence).toBe(7)

    // UUIDs should be different
    expect(newFunc.pui).not.toBe(original.pui)
    expect(newFunc.dui).not.toBe(original.dui)
  })
})
