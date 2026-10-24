import { describe, expect, it } from 'vitest'
import {
  convertUsdToInr,
  formatCompactInrAmount,
  formatInr,
  USD_TO_INR_RATE,
  USD_TO_INR_RATE_DATE,
} from '@/lib/utils'

describe('Indian rupee display conversion', () => {
  it('records the date for the configured indicative rate', () => {
    expect(USD_TO_INR_RATE_DATE).toBe('2026-10-23')
  })

  it('converts source USD amounts using the configured rate', () => {
    expect(convertUsdToInr(100)).toBe(100 * USD_TO_INR_RATE)
  })

  it('formats converted amounts with Indian digit grouping and the rupee symbol', () => {
    expect(formatInr(100)).toBe('₹9,494')
  })

  it('formats chart amounts in rupees without converting them twice', () => {
    expect(formatCompactInrAmount(9494000)).toContain('₹')
    expect(formatCompactInrAmount(9494000)).not.toContain('₹90')
  })

  it('returns a dash for missing currency amounts', () => {
    expect(convertUsdToInr(null)).toBeNull()
    expect(formatInr(null)).toBe('—')
  })
})
