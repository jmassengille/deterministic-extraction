/**
 * MSF Serializer Tests
 *
 * Tests serialization of normalized JSON back to MOX-compatible XML.
 * Validates roundtrip preservation and field ordering.
 */

import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { join } from 'path'
import { parseMSFXML, extractAllUUIDs } from '../../services/msfParser'
import { serializeMSFToXML } from '../../services/msfSerializer'

// Helper to load baseline MSF file
function loadBaselineMSF(filename: string): string {
  const basePath = join(process.cwd(), '../../../data/baseline')
  const fullPath = join(basePath, filename)
  return readFileSync(fullPath, 'utf-8')
}

describe('serializeMSFToXML', () => {
  it('serializes parsed document back to XML', () => {
    const xml = loadBaselineMSF('Digital Multimeters/Fluke 77 (Simple)/Fluke 77 Series II (Approved).msf')
    const parsed = parseMSFXML(xml)
    const serialized = serializeMSFToXML(parsed)

    // Should be valid XML
    expect(serialized).toContain('<?xml version="1.0" encoding="UTF-8"?>')
    expect(serialized).toContain('<instrument>')
    expect(serialized).toContain('</instrument>')
  })

  it('preserves all UUIDs in roundtrip', () => {
    const xml = loadBaselineMSF('Digital Multimeters/Fluke 77 (Simple)/Fluke 77 Series II (Approved).msf')
    const parsed = parseMSFXML(xml)
    const originalUUIDs = extractAllUUIDs(parsed)

    const serialized = serializeMSFToXML(parsed)
    const reparsed = parseMSFXML(serialized)
    const newUUIDs = extractAllUUIDs(reparsed)

    // All UUIDs must be identical after roundtrip
    expect(newUUIDs).toEqual(originalUUIDs)
  })

  it('converts booleans to MOX format (-1/0)', () => {
    const xml = loadBaselineMSF('Digital Multimeters/Fluke 77 (Simple)/Fluke 77 Series II (Approved).msf')
    const parsed = parseMSFXML(xml)
    const serialized = serializeMSFToXML(parsed)

    // verified = true should become -1
    expect(serialized).toContain('<verified>-1</verified>')

    // isoutput = false should become 0
    expect(serialized).toContain('<isoutput>0</isoutput>')
  })

  it('preserves empty tags', () => {
    const xml = loadBaselineMSF('Digital Multimeters/Fluke 77 (Simple)/Fluke 77 Series II (Approved).msf')
    const parsed = parseMSFXML(xml)
    const serialized = serializeMSFToXML(parsed)

    // Empty modifier should be <modifier></modifier>, not self-closing
    expect(serialized).toContain('<modifier></modifier>')
  })

  it('maintains field order matching baseline', () => {
    const xml = loadBaselineMSF('Digital Multimeters/Fluke 77 (Simple)/Fluke 77 Series II (Approved).msf')
    const parsed = parseMSFXML(xml)
    const serialized = serializeMSFToXML(parsed)

    // Extract tag order from serialized XML
    const tagPattern = /<(\w+)>/g
    const tags: string[] = []
    let match

    while ((match = tagPattern.exec(serialized)) !== null) {
      tags.push(match[1])
    }

    // Verify critical ordering: pui comes before dui
    const puiIndex = tags.indexOf('pui')
    const duiIndex = tags.indexOf('dui')
    expect(puiIndex).toBeLessThan(duiIndex)

    // Verify header comes before function
    const headerIndex = tags.indexOf('header')
    const functionIndex = tags.indexOf('function')
    expect(headerIndex).toBeLessThan(functionIndex)
  })

  it('handles functions array correctly', () => {
    const xml = loadBaselineMSF('Digital Multimeters/Fluke 77 (Simple)/Fluke 77 Series II (Approved).msf')
    const parsed = parseMSFXML(xml)
    const serialized = serializeMSFToXML(parsed)

    // Count function tags (should have 5 for Fluke 77)
    const functionCount = (serialized.match(/<function>/g) || []).length
    expect(functionCount).toBe(5)
  })

  it('preserves all data in roundtrip without loss', () => {
    const xml = loadBaselineMSF('Digital Multimeters/Fluke 77 (Simple)/Fluke 77 Series II (Approved).msf')
    const parsed1 = parseMSFXML(xml)
    const serialized = serializeMSFToXML(parsed1)
    const parsed2 = parseMSFXML(serialized)

    // Deep comparison of critical fields
    expect(parsed2.instrument.header.model).toBe(parsed1.instrument.header.model)
    expect(parsed2.instrument.header.manufacturer).toBe(parsed1.instrument.header.manufacturer)
    expect(parsed2.instrument.functions.length).toBe(parsed1.instrument.functions.length)
    expect(parsed2.instrument.functions[0].functionname).toBe(parsed1.instrument.functions[0].functionname)
  })

  it('handles modified document correctly', () => {
    const xml = loadBaselineMSF('Digital Multimeters/Fluke 77 (Simple)/Fluke 77 Series II (Approved).msf')
    const parsed = parseMSFXML(xml)

    // Modify a field
    parsed.instrument.functions[0].functionname = 'Modified Function Name'

    const serialized = serializeMSFToXML(parsed)
    const reparsed = parseMSFXML(serialized)

    // Modification should be preserved
    expect(reparsed.instrument.functions[0].functionname).toBe('Modified Function Name')

    // But UUIDs should still be preserved
    expect(reparsed.instrument.functions[0].pui).toBe(parsed.instrument.functions[0].pui)
  })
})
