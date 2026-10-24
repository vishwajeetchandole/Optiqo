import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import React from 'react'
import { StatusBanner } from '@/components/shared/StatusBanner'

describe('StatusBanner PRD Status Mapping', () => {
  it('renders "ok" variant correctly for optimal solver status', () => {
    render(
      <StatusBanner
        variant="ok"
        title="Valid plan ready"
        message="Optimal solution found within convergence tolerance"
      />
    )
    expect(screen.getByText('Valid plan ready')).toBeDefined()
    expect(screen.getByText('Optimal solution found within convergence tolerance')).toBeDefined()
    expect(screen.getByRole('status')).toBeDefined()
  })

  it('renders "warning" variant correctly for fallback or advisory plans', () => {
    render(
      <StatusBanner
        variant="warning"
        title="Plan available with warnings"
        message="Fallback forecast utilized for 2 SKUs"
      />
    )
    expect(screen.getByText('Plan available with warnings')).toBeDefined()
    expect(screen.getByText('Fallback forecast utilized for 2 SKUs')).toBeDefined()
  })

  it('renders "error" variant correctly for solver failure states (infeasible, timeout, error data)', () => {
    render(
      <StatusBanner
        variant="error"
        title="No valid plan available"
        message="Solver timed out or constraint infeasibility detected"
      />
    )
    expect(screen.getByText('No valid plan available')).toBeDefined()
    expect(screen.getByText('Solver timed out or constraint infeasibility detected')).toBeDefined()
  })

  it('renders custom action buttons when provided', () => {
    render(
      <StatusBanner
        variant="ok"
        title="Success"
        action={<button>Re-run Solver</button>}
      />
    )
    expect(screen.getByRole('button', { name: 'Re-run Solver' })).toBeDefined()
  })
})
