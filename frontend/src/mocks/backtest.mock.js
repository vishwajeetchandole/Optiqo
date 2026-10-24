import { sleep } from '../lib/utils'

/**
 * Backtest mock data and simulator.
 * PRD journeys J5, requirements P0-09, K1-K8.
 * Supports multiple benchmark scenarios, including a stress-test scenario
 * where Optiqo does NOT beat baseline to prove the UI reports honestly.
 */

// Daily series for chart tabs (30-day evaluation period)
export const MOCK_DAILY_METRICS = Array.from({ length: 30 }, (_, i) => {
  const day = `Day ${i + 1}`
  // Daily unmet demand (units)
  const b1_unmet = Math.max(0, Math.round(180 + Math.sin(i / 2) * 60 + (i % 5 === 0 ? 90 : 0)))
  const b2_unmet = Math.max(0, Math.round(110 + Math.sin(i / 2) * 40))
  const optiqo_unmet = Math.max(0, Math.round(20 + Math.sin(i / 3) * 15))

  // Daily expiry wastage (USD)
  const b1_expiry = Math.max(0, Math.round(2200 + Math.cos(i / 3) * 800))
  const b2_expiry = Math.max(0, Math.round(1400 + Math.cos(i / 3) * 500))
  const optiqo_expiry = Math.max(0, Math.round(350 + Math.cos(i / 4) * 150))

  // Daily freight cost (USD)
  const b1_freight = Math.round(2800 + (i % 4) * 300)
  const b2_freight = Math.round(3400 + (i % 3) * 450)
  const optiqo_freight = Math.round(3100 + Math.sin(i) * 300)

  return {
    day,
    b1_unmet,
    b2_unmet,
    optiqo_unmet,
    b1_expiry,
    b2_expiry,
    optiqo_expiry,
    b1_freight,
    b2_freight,
    optiqo_freight,
  }
})

// Scenario 1: Standard Benchmark (Optiqo Optimal)
export const SCENARIO_OPTIMAL = {
  scenarioId: 'standard_optimal',
  scenarioName: 'Standard Supply Chain Benchmark (FY24)',
  runId: 'bt-003',
  timestamp: '2024-11-15T08:00:00Z',
  evaluationWindow: '52 Weeks (FY2024)',
  seed: 42,
  parameters: {
    evalWindow: '52w',
    horizon: '12w',
    granularity: 'weekly',
    skusEvaluated: 340,
    nodesEvaluated: 8,
  },
  systemMetadata: {
    solverVersion: 'Optiqo MIP Engine v2.4.1-rc3',
    underlyingMip: 'HiGHS Linear & Integer Optimizer v1.7.0',
    dataset: 'demo-supply-chain-v1 (SIMULATED DATA)',
    ruleEngine: 'Invariant Checker v1.2',
  },
  // Gain decomposition: B1 -> B2 (Forecast Effect) and B2 -> Optiqo (Allocation Effect)
  gainDecomposition: [
    { name: 'B1 Baseline', value: 0, baseline: 0, fill: '#A3A3A3' },
    { name: 'Forecast Effect (B1→B2)', value: 42500, baseline: 0, fill: '#60A5FA' },
    { name: 'Allocation Effect (B2→Optiqo)', value: 68400, baseline: 42500, fill: '#7B68F5' },
    { name: 'Total Evaluated Net Benefit', value: 110900, baseline: 0, fill: '#10B981' },
  ],
  // PRD K1–K8 KPI comparison table
  kpis: [
    {
      id: 'K1',
      name: 'OTIF Service Level',
      unit: '%',
      threshold: '≥ 98.0%',
      b1: 91.4,
      b2: 95.8,
      optiqo: 98.9,
      diffVsB2Abs: 3.1,
      diffVsB2Rel: 3.2,
      b2BeatStatus: 'MET',
      thresholdStatus: 'MET',
    },
    {
      id: 'K2',
      name: 'Order Fill Rate',
      unit: '%',
      threshold: '≥ 99.0%',
      b1: 93.2,
      b2: 97.1,
      optiqo: 99.4,
      diffVsB2Abs: 2.3,
      diffVsB2Rel: 2.4,
      b2BeatStatus: 'MET',
      thresholdStatus: 'MET',
    },
    {
      id: 'K3',
      name: 'Total Stockout Duration',
      unit: 'days',
      threshold: '≤ 14 days',
      b1: 42,
      b2: 24,
      optiqo: 6,
      diffVsB2Abs: -18,
      diffVsB2Rel: -75.0,
      b2BeatStatus: 'MET',
      thresholdStatus: 'MET',
    },
    {
      id: 'K4',
      name: 'Expiry Wastage Loss',
      unit: 'USD',
      threshold: '≤ $50,000',
      b1: 98400,
      b2: 64200,
      optiqo: 18200,
      diffVsB2Abs: -46000,
      diffVsB2Rel: -71.7,
      b2BeatStatus: 'MET',
      thresholdStatus: 'MET',
    },
    {
      id: 'K5',
      name: 'Freight Transportation Cost',
      unit: 'USD',
      threshold: '≤ $150,000',
      b1: 142000,
      b2: 138500,
      optiqo: 124500,
      diffVsB2Abs: -14000,
      diffVsB2Rel: -10.1,
      b2BeatStatus: 'MET',
      thresholdStatus: 'MET',
    },
    {
      id: 'K6',
      name: 'Average Inventory Cover',
      unit: 'days',
      threshold: '25 – 45 days',
      b1: 58.2,
      b2: 44.5,
      optiqo: 34.1,
      diffVsB2Abs: -10.4,
      diffVsB2Rel: -23.4,
      b2BeatStatus: 'MET',
      thresholdStatus: 'MET',
    },
    {
      id: 'K7',
      name: 'Emergency Expedited Trips',
      unit: 'trips',
      threshold: '≤ 5 trips',
      b1: 16,
      b2: 9,
      optiqo: 2,
      diffVsB2Abs: -7,
      diffVsB2Rel: -77.8,
      b2BeatStatus: 'MET',
      thresholdStatus: 'MET',
    },
    {
      id: 'K8',
      name: 'Capacity Invariant Violations',
      unit: 'violations',
      threshold: '0',
      b1: 4,
      b2: 2,
      optiqo: 0,
      diffVsB2Abs: -2,
      diffVsB2Rel: -100.0,
      b2BeatStatus: 'MET',
      thresholdStatus: 'MET',
    },
  ],
  dailyMetrics: MOCK_DAILY_METRICS,
}

// Scenario 2: Stress-test / baseline parity where Optiqo does NOT beat baseline on freight
export const SCENARIO_STRESS_PARITY = {
  ...SCENARIO_OPTIMAL,
  scenarioId: 'stress_parity',
  scenarioName: 'Stress Test: Extreme Fuel Surcharge & Capacity Shock',
  runId: 'bt-004-stress',
  gainDecomposition: [
    { name: 'B1 Baseline', value: 0, baseline: 0, fill: '#A3A3A3' },
    { name: 'Forecast Effect (B1→B2)', value: 31000, baseline: 0, fill: '#60A5FA' },
    { name: 'Allocation Effect (B2→Optiqo)', value: -12400, baseline: 31000, fill: '#EF4444' },
    { name: 'Total Evaluated Net Benefit', value: 18600, baseline: 0, fill: '#10B981' },
  ],
  kpis: [
    {
      id: 'K1',
      name: 'OTIF Service Level',
      unit: '%',
      threshold: '≥ 98.0%',
      b1: 89.2,
      b2: 94.5,
      optiqo: 96.8, // Did not meet 98% threshold
      diffVsB2Abs: 2.3,
      diffVsB2Rel: 2.4,
      b2BeatStatus: 'MET',
      thresholdStatus: 'NOT_MET',
    },
    {
      id: 'K2',
      name: 'Order Fill Rate',
      unit: '%',
      threshold: '≥ 99.0%',
      b1: 91.0,
      b2: 96.2,
      optiqo: 97.9, // Did not meet 99% threshold
      diffVsB2Abs: 1.7,
      diffVsB2Rel: 1.8,
      b2BeatStatus: 'MET',
      thresholdStatus: 'NOT_MET',
    },
    {
      id: 'K3',
      name: 'Total Stockout Duration',
      unit: 'days',
      threshold: '≤ 14 days',
      b1: 48,
      b2: 29,
      optiqo: 18, // Did not meet 14 days threshold
      diffVsB2Abs: -11,
      diffVsB2Rel: -37.9,
      b2BeatStatus: 'MET',
      thresholdStatus: 'NOT_MET',
    },
    {
      id: 'K4',
      name: 'Expiry Wastage Loss',
      unit: 'USD',
      threshold: '≤ $50,000',
      b1: 112000,
      b2: 78000,
      optiqo: 42000,
      diffVsB2Abs: -36000,
      diffVsB2Rel: -46.2,
      b2BeatStatus: 'MET',
      thresholdStatus: 'MET',
    },
    {
      id: 'K5',
      name: 'Freight Transportation Cost',
      unit: 'USD',
      threshold: '≤ $150,000',
      b1: 138000,
      b2: 142000,
      optiqo: 164000, // Optiqo HIGHER freight than B2 due to emergency transfers!
      diffVsB2Abs: 22000,
      diffVsB2Rel: 15.5,
      b2BeatStatus: 'NOT_MET',
      thresholdStatus: 'NOT_MET',
    },
    {
      id: 'K6',
      name: 'Average Inventory Cover',
      unit: 'days',
      threshold: '25 – 45 days',
      b1: 62.0,
      b2: 48.0,
      optiqo: 38.0,
      diffVsB2Abs: -10.0,
      diffVsB2Rel: -20.8,
      b2BeatStatus: 'MET',
      thresholdStatus: 'MET',
    },
    {
      id: 'K7',
      name: 'Emergency Expedited Trips',
      unit: 'trips',
      threshold: '≤ 5 trips',
      b1: 22,
      b2: 14,
      optiqo: 8, // Did not meet 5 trips threshold
      diffVsB2Abs: -6,
      diffVsB2Rel: -42.8,
      b2BeatStatus: 'MET',
      thresholdStatus: 'NOT_MET',
    },
    {
      id: 'K8',
      name: 'Capacity Invariant Violations',
      unit: 'violations',
      threshold: '0',
      b1: 6,
      b2: 3,
      optiqo: 0,
      diffVsB2Abs: -3,
      diffVsB2Rel: -100.0,
      b2BeatStatus: 'MET',
      thresholdStatus: 'MET',
    },
  ],
  dailyMetrics: MOCK_DAILY_METRICS,
}

/**
 * Fetch backtest summary and KPI comparison.
 * @param {{ scenario?: string }} params
 */
export async function getBacktestSummary({ scenario = 'standard_optimal' } = {}) {
  await sleep(400)
  if (scenario === 'stress_parity') {
    return { source: 'mock', ...SCENARIO_STRESS_PARITY }
  }
  return { source: 'mock', ...SCENARIO_OPTIMAL }
}

/**
 * Trigger backtest run with staged progress simulation.
 */
export async function triggerBacktest(_config = {}) {
  await sleep(300)
  return { source: 'mock', runId: 'bt-005', status: 'QUEUED', queued: true }
}

/**
 * Fetch historical backtest runs.
 */
export async function getBacktestHistory({ page = 1, pageSize = 10 } = {}) {
  await sleep(250)
  return {
    source: 'mock',
    items: [
      { runId: 'bt-003', timestamp: '2024-11-15T08:00:00Z', status: 'OK', seed: 42, window: '52w', otifScore: 98.9 },
      { runId: 'bt-002', timestamp: '2024-11-08T09:30:00Z', status: 'OK', seed: 101, window: '26w', otifScore: 97.4 },
      { runId: 'bt-001', timestamp: '2024-11-01T14:15:00Z', status: 'CHECK_FAILED', seed: 99, window: '12w', otifScore: 94.1 },
    ],
    total: 3,
    page,
    pageSize,
  }
}
