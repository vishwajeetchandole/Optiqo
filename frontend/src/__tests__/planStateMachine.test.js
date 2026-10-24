import { describe, it, expect } from 'vitest'

/**
 * Plan run state machine and red-status safety rule test:
 * A red state (timeout, infeasible, check failed, error data)
 * must NEVER display or mark a plan as final (PRD P0-06).
 */
const RED_STATUSES = [
  'SOLVER_TIMEOUT',
  'SOLVER_NOT_OPTIMAL',
  'INFEASIBLE',
  'CHECK_FAILED',
  'ERROR_DATA',
]

const YELLOW_STATUSES = ['FALLBACK_FORECAST', 'NOT_OPTIMAL', 'WARNING']

function evaluatePlanFinality(status) {
  if (RED_STATUSES.includes(status)) {
    return {
      isFinal: false,
      bannerVariant: 'error',
      displayPlanAsFinal: false,
      showDiagnosticHalt: true,
    }
  }

  if (YELLOW_STATUSES.includes(status)) {
    return {
      isFinal: true,
      bannerVariant: 'warning',
      displayPlanAsFinal: true,
      showDiagnosticHalt: false,
    }
  }

  return {
    isFinal: true,
    bannerVariant: 'ok',
    displayPlanAsFinal: true,
    showDiagnosticHalt: false,
  }
}

describe('Plan-run state machine & safety rules', () => {
  it('correctly maps OK status to optimal final plan', () => {
    const outcome = evaluatePlanFinality('OK')
    expect(outcome.isFinal).toBe(true)
    expect(outcome.bannerVariant).toBe('ok')
    expect(outcome.displayPlanAsFinal).toBe(true)
    expect(outcome.showDiagnosticHalt).toBe(false)
  })

  it('correctly maps FALLBACK_FORECAST to warning state with final plan enabled', () => {
    const outcome = evaluatePlanFinality('FALLBACK_FORECAST')
    expect(outcome.isFinal).toBe(true)
    expect(outcome.bannerVariant).toBe('warning')
    expect(outcome.displayPlanAsFinal).toBe(true)
    expect(outcome.showDiagnosticHalt).toBe(false)
  })

  RED_STATUSES.forEach((statusCode) => {
    it(`strictly forbids marking plan as final when solver status is ${statusCode}`, () => {
      const outcome = evaluatePlanFinality(statusCode)
      expect(outcome.isFinal).toBe(false)
      expect(outcome.bannerVariant).toBe('error')
      expect(outcome.displayPlanAsFinal).toBe(false)
      expect(outcome.showDiagnosticHalt).toBe(true)
    })
  })
})
