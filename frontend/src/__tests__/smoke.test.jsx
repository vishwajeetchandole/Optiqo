import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import React from 'react'

import Overview from '@/pages/Overview'
import DataValidation from '@/pages/DataValidation'
import RiskOverview from '@/pages/RiskOverview'
import DistributionPlan from '@/pages/DistributionPlan'
import RecommendationDetail from '@/pages/RecommendationDetail'
import Backtesting from '@/pages/Backtesting'
import RunDetails from '@/pages/RunDetails'

// Mock ResizeObserver which Recharts uses
globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

describe('Application Page Smoke Tests', () => {
  it('renders Overview page without crashing', () => {
    const { container } = render(
      <MemoryRouter>
        <Overview />
      </MemoryRouter>
    )
    expect(container).toBeDefined()
  })

  it('renders DataValidation page without crashing', () => {
    const { container } = render(
      <MemoryRouter>
        <DataValidation />
      </MemoryRouter>
    )
    expect(container).toBeDefined()
  })

  it('renders RiskOverview page without crashing', () => {
    const { container } = render(
      <MemoryRouter>
        <RiskOverview />
      </MemoryRouter>
    )
    expect(container).toBeDefined()
  })

  it('renders DistributionPlan page without crashing', () => {
    const { container } = render(
      <MemoryRouter>
        <DistributionPlan />
      </MemoryRouter>
    )
    expect(container).toBeDefined()
  })

  it('renders RecommendationDetail page without crashing', () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/plan/line-001']}>
        <Routes>
          <Route path="/plan/:lineId" element={<RecommendationDetail />} />
        </Routes>
      </MemoryRouter>
    )
    expect(container).toBeDefined()
  })

  it('renders Backtesting page without crashing', () => {
    const { container } = render(
      <MemoryRouter>
        <Backtesting />
      </MemoryRouter>
    )
    expect(container).toBeDefined()
  })

  it('renders RunDetails page without crashing', () => {
    const { container } = render(
      <MemoryRouter>
        <RunDetails />
      </MemoryRouter>
    )
    expect(container).toBeDefined()
  })
})
