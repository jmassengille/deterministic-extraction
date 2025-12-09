/**
 * MSF Template Extractor
 *
 * Extracts function templates from MSF documents.
 * Templates preserve structure but strip UUIDs and specific values.
 *
 * Use cases:
 * - Extract templates from baseline MSF files
 * - Create new functions from templates
 * - Copy function structure within document
 */

import type {
  MSFFunctionNormalized,
  MSFRangeNormalized,
  MSFSpecificationNormalized,
  MSFParameterNormalized
} from '../types/msf.types'
import { generateMOXUUID } from './uuidGenerator'

/**
 * Function template with all UUIDs removed.
 * Used as blueprint for creating new functions.
 */
export interface FunctionTemplate {
  functionname: string
  modifier: string | null
  properties: string
  format: string
  isoutput: boolean
  ranges: RangeTemplate[]
}

export interface RangeTemplate {
  rangename: string
  rangeid: string
  properties: string
  autoassign: boolean
  parameter: ParameterTemplate
  specifications: SpecificationTemplate[]
}

export interface ParameterTemplate {
  lowerlimit: number
  upperlimit: number
  unitofmeasure: string
  unitsymbol: string
  isbipolar: boolean
  paramname: string
}

export interface SpecificationTemplate {
  calinterval: number
  Specialcal: string
  AssetNum: string
  spectype: string
  unitofmeasure: string
  unitsymbol: string
  fullscale: number
  iv_pct: number
  iv_pct_hi: number
  iv_ppm: number
  fs_pct: number
  fs_pct_hi: number
  fs_ppm: number
  floor: number
  floor_hi: number
  db: number
  dbtype: number
  calcdesc: string
  calcstring: string
  operand: string
}

/**
 * Extract function template from existing function.
 * Strips UUIDs, metadata, and UI-only fields.
 *
 * @param func - Source function
 * @returns Function template (structure without UUIDs)
 */
export function extractFunctionTemplate(func: MSFFunctionNormalized): FunctionTemplate {
  return {
    functionname: func.functionname,
    modifier: func.modifier,
    properties: func.properties,
    format: func.format,
    isoutput: func.isoutput,
    ranges: func.ranges.map(extractRangeTemplate)
  }
}

/**
 * Extract range template from existing range.
 */
function extractRangeTemplate(range: MSFRangeNormalized): RangeTemplate {
  return {
    rangename: range.rangename,
    rangeid: range.rangeid,
    properties: range.properties,
    autoassign: range.autoassign,
    parameter: extractParameterTemplate(range.parameter),
    specifications: range.specifications.map(extractSpecificationTemplate)
  }
}

/**
 * Extract parameter template from existing parameter.
 */
function extractParameterTemplate(param: MSFParameterNormalized): ParameterTemplate {
  return {
    lowerlimit: param.lowerlimit,
    upperlimit: param.upperlimit,
    unitofmeasure: param.unitofmeasure,
    unitsymbol: param.unitsymbol,
    isbipolar: param.isbipolar,
    paramname: param.paramname
  }
}

/**
 * Extract specification template from existing specification.
 */
function extractSpecificationTemplate(spec: MSFSpecificationNormalized): SpecificationTemplate {
  return {
    calinterval: spec.calinterval,
    Specialcal: spec.Specialcal,
    AssetNum: spec.AssetNum,
    spectype: spec.spectype,
    unitofmeasure: spec.unitofmeasure,
    unitsymbol: spec.unitsymbol,
    fullscale: spec.fullscale,
    iv_pct: spec.iv_pct,
    iv_pct_hi: spec.iv_pct_hi,
    iv_ppm: spec.iv_ppm,
    fs_pct: spec.fs_pct,
    fs_pct_hi: spec.fs_pct_hi,
    fs_ppm: spec.fs_ppm,
    floor: spec.floor,
    floor_hi: spec.floor_hi,
    db: spec.db,
    dbtype: spec.dbtype,
    calcdesc: spec.calcdesc,
    calcstring: spec.calcstring,
    operand: spec.operand
  }
}

/**
 * Create new function from template.
 * Generates fresh UUIDs for all entities.
 *
 * @param template - Function template
 * @param sequence - Sequence number for the function
 * @returns Fully-formed function with new UUIDs
 */
export function createFunctionFromTemplate(
  template: FunctionTemplate,
  sequence: number
): MSFFunctionNormalized {
  return {
    pui: generateMOXUUID(),
    dui: generateMOXUUID(),
    sequence,
    functionname: template.functionname,
    modifier: template.modifier,
    properties: template.properties,
    format: template.format,
    isoutput: template.isoutput,
    noteidlist: '',
    verified: false,
    review: false,
    ranges: template.ranges.map((rangeTemplate, idx) =>
      createRangeFromTemplate(rangeTemplate, idx)
    ),
    _uiExpanded: false,
    _uiStatus: 'unreviewed'
  }
}

/**
 * Create new range from template.
 */
function createRangeFromTemplate(
  template: RangeTemplate,
  sequence: number
): MSFRangeNormalized {
  return {
    pui: generateMOXUUID(),
    dui: generateMOXUUID(),
    sequence,
    rangename: template.rangename,
    rangeid: template.rangeid,
    properties: template.properties,
    autoassign: template.autoassign,
    noteidlist: '',
    verified: false,
    review: false,
    parameter: createParameterFromTemplate(template.parameter),
    specifications: template.specifications.map((specTemplate, idx) =>
      createSpecificationFromTemplate(specTemplate, idx)
    )
  }
}

/**
 * Create new parameter from template.
 */
function createParameterFromTemplate(template: ParameterTemplate): MSFParameterNormalized {
  return {
    pui: generateMOXUUID(),
    dui: generateMOXUUID(),
    sequence: 0,
    lowerlimit: template.lowerlimit,
    upperlimit: template.upperlimit,
    unitofmeasure: template.unitofmeasure,
    unitsymbol: template.unitsymbol,
    isbipolar: template.isbipolar,
    noteidlist: '',
    paramname: template.paramname,
    verified: false,
    review: false
  }
}

/**
 * Create new specification from template.
 */
function createSpecificationFromTemplate(
  template: SpecificationTemplate,
  sequence: number
): MSFSpecificationNormalized {
  return {
    pui: generateMOXUUID(),
    dui: generateMOXUUID(),
    sequence,
    calinterval: template.calinterval,
    Specialcal: template.Specialcal,
    AssetNum: template.AssetNum,
    spectype: template.spectype,
    unitofmeasure: template.unitofmeasure,
    unitsymbol: template.unitsymbol,
    fullscale: template.fullscale,
    iv_pct: template.iv_pct,
    iv_pct_hi: template.iv_pct_hi,
    iv_ppm: template.iv_ppm,
    fs_pct: template.fs_pct,
    fs_pct_hi: template.fs_pct_hi,
    fs_ppm: template.fs_ppm,
    floor: template.floor,
    floor_hi: template.floor_hi,
    db: template.db,
    dbtype: template.dbtype,
    calcdesc: template.calcdesc,
    calcstring: template.calcstring,
    operand: template.operand
  }
}

/**
 * Pre-defined function templates for common instrument types.
 * These can be used when no document is loaded or for quick function creation.
 */
export const PREDEFINED_TEMPLATES: Record<string, FunctionTemplate> = {
  'voltage-dc': {
    functionname: 'Voltage, DC',
    modifier: null,
    properties: '',
    format: '',
    isoutput: false,
    ranges: [
      {
        rangename: 'Default Range',
        rangeid: '',
        properties: '',
        autoassign: true,
        parameter: {
          lowerlimit: 0,
          upperlimit: 100,
          unitofmeasure: 'volt',
          unitsymbol: 'V',
          isbipolar: true,
          paramname: ''
        },
        specifications: [
          {
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
    ]
  },

  'voltage-ac': {
    functionname: 'Voltage, AC',
    modifier: null,
    properties: '',
    format: '',
    isoutput: false,
    ranges: [
      {
        rangename: 'Default Range',
        rangeid: '',
        properties: '',
        autoassign: true,
        parameter: {
          lowerlimit: 0,
          upperlimit: 100,
          unitofmeasure: 'volt',
          unitsymbol: 'V',
          isbipolar: false,
          paramname: ''
        },
        specifications: [
          {
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
    ]
  },

  'resistance': {
    functionname: 'Resistance',
    modifier: null,
    properties: '',
    format: '',
    isoutput: false,
    ranges: [
      {
        rangename: 'Default Range',
        rangeid: '',
        properties: '',
        autoassign: true,
        parameter: {
          lowerlimit: 0,
          upperlimit: 1000,
          unitofmeasure: 'ohm',
          unitsymbol: 'Ω',
          isbipolar: false,
          paramname: ''
        },
        specifications: [
          {
            calinterval: 365,
            Specialcal: '',
            AssetNum: '',
            spectype: 'Accuracy',
            unitofmeasure: 'ohm',
            unitsymbol: 'Ω',
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
    ]
  },

  'current-dc': {
    functionname: 'Current, DC',
    modifier: null,
    properties: '',
    format: '',
    isoutput: false,
    ranges: [
      {
        rangename: 'Default Range',
        rangeid: '',
        properties: '',
        autoassign: true,
        parameter: {
          lowerlimit: 0,
          upperlimit: 10,
          unitofmeasure: 'ampere',
          unitsymbol: 'A',
          isbipolar: true,
          paramname: ''
        },
        specifications: [
          {
            calinterval: 365,
            Specialcal: '',
            AssetNum: '',
            spectype: 'Accuracy',
            unitofmeasure: 'ampere',
            unitsymbol: 'A',
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
    ]
  }
}

/**
 * Get list of available pre-defined template keys.
 */
export function getAvailableTemplates(): string[] {
  return Object.keys(PREDEFINED_TEMPLATES)
}

/**
 * Get template by key.
 *
 * @param key - Template key (e.g., 'voltage-dc')
 * @returns Template or null if not found
 */
export function getTemplate(key: string): FunctionTemplate | null {
  return PREDEFINED_TEMPLATES[key] || null
}
