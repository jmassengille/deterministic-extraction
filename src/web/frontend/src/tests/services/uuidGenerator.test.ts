/**
 * UUID Generator Tests
 */

import { describe, it, expect } from 'vitest'
import { generateMOXUUID, isValidMOXUUID, generateNullUUID } from '../../services/uuidGenerator'

describe('generateMOXUUID', () => {
  it('generates UUID in MOX format with braces', () => {
    const uuid = generateMOXUUID()
    expect(uuid).toMatch(/^\{[0-9A-F-]+\}$/)
  })

  it('generates uppercase UUID', () => {
    const uuid = generateMOXUUID()
    expect(uuid).toBe(uuid.toUpperCase())
  })

  it('generates valid UUID structure', () => {
    const uuid = generateMOXUUID()
    expect(uuid).toMatch(/^\{[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}\}$/)
  })

  it('generates unique UUIDs', () => {
    const uuid1 = generateMOXUUID()
    const uuid2 = generateMOXUUID()
    expect(uuid1).not.toBe(uuid2)
  })
})

describe('isValidMOXUUID', () => {
  it('validates correct MOX UUID format', () => {
    expect(isValidMOXUUID('{909A9194-0F64-457A-B5C4-04BA19963EB1}')).toBe(true)
    expect(isValidMOXUUID('{00000000-0000-0000-0000-000000000000}')).toBe(true)
  })

  it('rejects UUID without braces', () => {
    expect(isValidMOXUUID('909A9194-0F64-457A-B5C4-04BA19963EB1')).toBe(false)
  })

  it('rejects lowercase UUID', () => {
    expect(isValidMOXUUID('{909a9194-0f64-457a-b5c4-04ba19963eb1}')).toBe(false)
  })

  it('rejects malformed UUIDs', () => {
    expect(isValidMOXUUID('{909A9194}')).toBe(false)
    expect(isValidMOXUUID('')).toBe(false)
    expect(isValidMOXUUID('not-a-uuid')).toBe(false)
  })
})

describe('generateNullUUID', () => {
  it('generates null UUID', () => {
    const uuid = generateNullUUID()
    expect(uuid).toBe('{00000000-0000-0000-0000-000000000000}')
  })

  it('generates valid MOX format', () => {
    const uuid = generateNullUUID()
    expect(isValidMOXUUID(uuid)).toBe(true)
  })
})
