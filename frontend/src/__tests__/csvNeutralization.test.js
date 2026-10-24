import { describe, it, expect } from 'vitest'

/**
 * PRD P0-11: Spreadsheet Formula Injection Neutralizer
 * Prevents execution of malicious formulas in Excel / Google Sheets
 * by prepending a single quote (') to cells starting with =, +, -, or @.
 */
function sanitizeCsvCell(val) {
  if (val == null) return ''
  const str = String(val)
  if (['=', '+', '-', '@'].includes(str.charAt(0))) {
    return `'${str}`
  }
  return str.includes(',') ? `"${str}"` : str
}

describe('PRD P0-11: CSV Formula Injection Neutralization', () => {
  it('neutralizes cells starting with =', () => {
    expect(sanitizeCsvCell('=SUM(A1:A10)')).toBe("'=SUM(A1:A10)")
    expect(sanitizeCsvCell('=cmd|/C calc!A0')).toBe(" benefit: '=cmd|/C calc!A0".replace(' benefit: ', ''))
  })

  it('neutralizes cells starting with +', () => {
    expect(sanitizeCsvCell('+12345')).toBe("'+12345")
    expect(sanitizeCsvCell('+cmd|/C calc!A0')).toBe("'+cmd|/C calc!A0")
  })

  it('neutralizes cells starting with -', () => {
    expect(sanitizeCsvCell('-12.5%')).toBe("'-12.5%")
    expect(sanitizeCsvCell('-cmd|/C calc!A0')).toBe("'-cmd|/C calc!A0")
  })

  it('neutralizes cells starting with @', () => {
    expect(sanitizeCsvCell('@SUM(A1:A10)')).toBe("'@SUM(A1:A10)")
    expect(sanitizeCsvCell('@attacker.com')).toBe("'@attacker.com")
  })

  it('leaves standard benign strings and numbers unchanged', () => {
    expect(sanitizeCsvCell('SKU-1042')).toBe('SKU-1042')
    expect(sanitizeCsvCell('WH-1 (Newark DC)')).toBe('WH-1 (Newark DC)')
    expect(sanitizeCsvCell(1450)).toBe('1450')
  })

  it('escapes cells containing commas with double quotes', () => {
    expect(sanitizeCsvCell('Vaccine, Pediatric')).toBe('"Vaccine, Pediatric"')
  })
})
