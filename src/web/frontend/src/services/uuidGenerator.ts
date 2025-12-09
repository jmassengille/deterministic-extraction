/**
 * MOX-Compatible UUID Generator
 *
 * Requirements from baseline analysis:
 * - Format: {XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}
 * - Uppercase letters
 * - Braces required
 * - Used for pui (Primary Universal Identifier) and dui fields
 */

/**
 * Generate MOX-compatible UUID.
 * Uses browser native crypto.randomUUID() and formats for MOX.
 *
 * @returns UUID in format {XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}
 *
 * @example
 * generateMOXUUID()
 * // Returns: "{909A9194-0F64-457A-B5C4-04BA19963EB1}"
 */
export function generateMOXUUID(): string {
  const uuid = crypto.randomUUID().toUpperCase()
  return `{${uuid}}`
}

/**
 * Validate UUID format matches MOX requirements.
 *
 * @param uuid - UUID string to validate
 * @returns true if valid MOX format, false otherwise
 *
 * @example
 * isValidMOXUUID("{909A9194-0F64-457A-B5C4-04BA19963EB1}")
 * // Returns: true
 *
 * isValidMOXUUID("909A9194-0F64-457A-B5C4-04BA19963EB1")
 * // Returns: false (missing braces)
 */
export function isValidMOXUUID(uuid: string): boolean {
  const pattern = /^\{[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}\}$/
  return pattern.test(uuid)
}

/**
 * Generate a null/empty UUID placeholder.
 * Some MOX fields use empty UUIDs.
 *
 * @returns Empty UUID in format {00000000-0000-0000-0000-000000000000}
 */
export function generateNullUUID(): string {
  return '{00000000-0000-0000-0000-000000000000}'
}
