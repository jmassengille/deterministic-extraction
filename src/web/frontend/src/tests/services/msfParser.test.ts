/**
 * MSF Parser Tests
 *
 * Tests parsing of MSF XML files to normalized JSON format.
 * Uses real baseline MSF files to ensure compatibility.
 */

import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { join } from 'path'
import { parseMSFXML, extractAllUUIDs } from '../../services/msfParser'

// Helper to load baseline MSF file
function loadBaselineMSF(filename: string): string {
  const basePath = join(process.cwd(), '../../../data/baseline')
  const fullPath = join(basePath, filename)
  return readFileSync(fullPath, 'utf-8')
}

describe('parseMSFXML', () => {
  it('parses simple baseline MSF (Fluke 77)', () => {
    const xml = loadBaselineMSF('Digital Multimeters/Fluke 77 (Simple)/Fluke 77 Series II (Approved).msf')
    const parsed = parseMSFXML(xml)

    expect(parsed).toBeDefined()
    expect(parsed.instrument).toBeDefined()
    expect(parsed.instrument.header).toBeDefined()
    expect(parsed.instrument.functions).toBeInstanceOf(Array)
  })

  it('preserves UUIDs from baseline file', () => {
    const xml = loadBaselineMSF('Digital Multimeters/Fluke 77 (Simple)/Fluke 77 Series II (Approved).msf')
    const parsed = parseMSFXML(xml)

    // Check root UUIDs
    expect(parsed.instrument.pui).toBe('{909A9194-0F64-457A-B5C4-04BA19963EB1}')
    expect(parsed.instrument.dui).toBe('{C6DC1294-2396-404E-8B59-E7D7090F83CF}')

    // Check header UUIDs
    expect(parsed.instrument.header.pui).toBe('{47272B9E-EC17-4D1C-9782-4C356736B87D}')
    expect(parsed.instrument.header.dui).toBe('{6B8B6487-9160-4353-B450-6CD918B0CE29}')

    // Check first function UUID
    expect(parsed.instrument.functions[0].pui).toBe('{847C7C92-F281-49D3-8A40-0FA7E4DA88AB}')
  })

  it('normalizes single function to array', () => {
    const xml = `<?xml version="1.0"?>
      <instrument>
        <pui>{TEST1}</pui>
        <dui>{TEST2}</dui>
        <verified>0</verified>
        <review>0</review>
        <filenotes></filenotes>
        <filehistory></filehistory>
        <header>
          <pui>{HEADER1}</pui>
          <dui>{HEADER2}</dui>
          <model>Test</model>
          <manufacturer>Test</manufacturer>
          <description>Test</description>
          <confidence>0</confidence>
          <confidenceDesc></confidenceDesc>
          <specreference></specreference>
          <author></author>
          <verifiedby></verifiedby>
          <approvedby></approvedby>
          <approvedate></approvedate>
          <save_date></save_date>
          <saved_by></saved_by>
          <revision>0</revision>
          <app_name></app_name>
          <app_version></app_version>
          <source_filename></source_filename>
          <source_date></source_date>
          <lims_widgetcode>0</lims_widgetcode>
          <lims_equipclass>0</lims_equipclass>
          <noteidlist></noteidlist>
          <isactive>0</isactive>
          <verified>0</verified>
          <review>0</review>
          <revisionnotes></revisionnotes>
        </header>
        <function>
          <pui>{FUNC1}</pui>
          <dui>{FUNC2}</dui>
          <sequence>0</sequence>
          <functionname>Test Function</functionname>
          <modifier></modifier>
          <properties></properties>
          <format></format>
          <isoutput>0</isoutput>
          <noteidlist></noteidlist>
          <verified>0</verified>
          <review>0</review>
        </function>
      </instrument>`

    const parsed = parseMSFXML(xml)
    expect(parsed.instrument.functions).toBeInstanceOf(Array)
    expect(parsed.instrument.functions).toHaveLength(1)
  })

  it('converts MOX booleans to JavaScript booleans', () => {
    const xml = loadBaselineMSF('Digital Multimeters/Fluke 77 (Simple)/Fluke 77 Series II (Approved).msf')
    const parsed = parseMSFXML(xml)

    // Root verified should be true (-1 in XML)
    expect(parsed.instrument.verified).toBe(true)

    // Functions have isoutput = 0 (false)
    expect(parsed.instrument.functions[0].isoutput).toBe(false)
  })

  it('normalizes empty modifier to null', () => {
    const xml = loadBaselineMSF('Digital Multimeters/Fluke 77 (Simple)/Fluke 77 Series II (Approved).msf')
    const parsed = parseMSFXML(xml)

    // First function has empty modifier in XML
    expect(parsed.instrument.functions[0].modifier).toBeNull()
  })

  it('handles functions with 5 functions correctly', () => {
    const xml = loadBaselineMSF('Digital Multimeters/Fluke 77 (Simple)/Fluke 77 Series II (Approved).msf')
    const parsed = parseMSFXML(xml)

    expect(parsed.instrument.functions).toHaveLength(5)
  })

  it('throws error for invalid XML', () => {
    expect(() => parseMSFXML('not xml')).toThrow()
  })

  it('throws error for missing instrument root', () => {
    const invalidXML = '<?xml version="1.0"?><notinstrument></notinstrument>'
    expect(() => parseMSFXML(invalidXML)).toThrow(/missing.*instrument/i)
  })
})

describe('extractAllUUIDs', () => {
  it('extracts all UUIDs from document', () => {
    const xml = loadBaselineMSF('Digital Multimeters/Fluke 77 (Simple)/Fluke 77 Series II (Approved).msf')
    const parsed = parseMSFXML(xml)
    const uuids = extractAllUUIDs(parsed)

    // Should have UUIDs from:
    // - instrument (2)
    // - header (2)
    // - 5 functions × 2 = 10
    // - ranges, parameters, specs (many more)
    expect(uuids.length).toBeGreaterThan(14)
    expect(uuids.every(uuid => uuid.match(/^\{[0-9A-F-]+\}$/))).toBe(true)
  })
})
