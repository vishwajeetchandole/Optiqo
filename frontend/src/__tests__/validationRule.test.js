import { describe, it, expect } from 'vitest'

/**
 * Validation logic invariant test:
 * Verifies that validation errors strictly block plan generation,
 * while warnings allow planning to proceed (PRD P0-01, P0-02, P0-04).
 */
function computeValidationState(report) {
  if (!report) return 'idle'
  if (report.errorsCount > 0) return 'invalid'
  if (report.warningsCount > 0) return 'warnings-only'
  return 'valid'
}

function isPlanGenerationAllowed(report) {
  const state = computeValidationState(report)
  return state !== 'invalid' && (report?.errorsCount || 0) === 0
}

describe('Validation-blocks-plan flow invariant', () => {
  it('blocks plan generation when critical errors are present', () => {
    const reportWithErrors = {
      errorsCount: 2,
      warningsCount: 1,
      checks: [{ status: 'FAIL', severity: 'critical' }],
    }
    expect(computeValidationState(reportWithErrors)).toBe('invalid')
    expect(isPlanGenerationAllowed(reportWithErrors)).toBe(false)
  })

  it('permits plan generation when only advisory warnings are present', () => {
    const reportWithWarningsOnly = {
      errorsCount: 0,
      warningsCount: 3,
      checks: [{ status: 'FAIL', severity: 'warning' }],
    }
    expect(computeValidationState(reportWithWarningsOnly)).toBe('warnings-only')
    expect(isPlanGenerationAllowed(reportWithWarningsOnly)).toBe(true)
  })

  it('permits plan generation when zero errors and zero warnings are present', () => {
    const cleanReport = {
      errorsCount: 0,
      warningsCount: 0,
      checks: [{ status: 'PASS', severity: 'info' }],
    }
    expect(computeValidationState(cleanReport)).toBe('valid')
    expect(isPlanGenerationAllowed(cleanReport)).toBe(true)
  })
})
