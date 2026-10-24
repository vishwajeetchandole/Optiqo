import { sleep } from '../lib/utils'

/**
 * Overview mock — single endpoint that aggregates all data the Overview page needs.
 * All values sourced from the mock; tagged source:"mock".
 */

/** Deterministic weekly demand forecast series (Network total) */
const NETWORK_SERIES = [
  { week: 'W01', actual: 1842, forecast: 1900, lowerBound: 1520, upperBound: 2280 },
  { week: 'W02', actual: 2103, forecast: 1950, lowerBound: 1560, upperBound: 2340 },
  { week: 'W03', actual: 1756, forecast: 1980, lowerBound: 1584, upperBound: 2376 },
  { week: 'W04', actual: 2280, forecast: 2020, lowerBound: 1616, upperBound: 2424 },
  { week: 'W05', actual: null, forecast: 2050, lowerBound: 1640, upperBound: 2460 },
  { week: 'W06', actual: null, forecast: 2100, lowerBound: 1680, upperBound: 2520 },
  { week: 'W07', actual: null, forecast: 1980, lowerBound: 1584, upperBound: 2376 },
  { week: 'W08', actual: null, forecast: 2200, lowerBound: 1760, upperBound: 2640 },
  { week: 'W09', actual: null, forecast: 2150, lowerBound: 1720, upperBound: 2580 },
  { week: 'W10', actual: null, forecast: 2350, lowerBound: 1880, upperBound: 2820 },
  { week: 'W11', actual: null, forecast: 2400, lowerBound: 1920, upperBound: 2880 },
  { week: 'W12', actual: null, forecast: 2280, lowerBound: 1824, upperBound: 2736 },
]

const SKU_SERIES = {
  'SKU-1042': [
    { week: 'W01', actual: 184, forecast: 190, lowerBound: 152, upperBound: 228 },
    { week: 'W02', actual: 210, forecast: 195, lowerBound: 156, upperBound: 234 },
    { week: 'W03', actual: 175, forecast: 198, lowerBound: 158, upperBound: 238 },
    { week: 'W04', actual: 228, forecast: 202, lowerBound: 162, upperBound: 242 },
    { week: 'W05', actual: null, forecast: 205, lowerBound: 164, upperBound: 246 },
    { week: 'W06', actual: null, forecast: 210, lowerBound: 168, upperBound: 252 },
    { week: 'W07', actual: null, forecast: 198, lowerBound: 158, upperBound: 238 },
    { week: 'W08', actual: null, forecast: 220, lowerBound: 176, upperBound: 264 },
    { week: 'W09', actual: null, forecast: 215, lowerBound: 172, upperBound: 258 },
    { week: 'W10', actual: null, forecast: 235, lowerBound: 188, upperBound: 282 },
    { week: 'W11', actual: null, forecast: 240, lowerBound: 192, upperBound: 288 },
    { week: 'W12', actual: null, forecast: 228, lowerBound: 182, upperBound: 274 },
  ],
  'SKU-2198': [
    { week: 'W01', actual: 92,  forecast: 95,  lowerBound: 76, upperBound: 114 },
    { week: 'W02', actual: 105, forecast: 98,  lowerBound: 78, upperBound: 118 },
    { week: 'W03', actual: 88,  forecast: 99,  lowerBound: 79, upperBound: 119 },
    { week: 'W04', actual: 114, forecast: 101, lowerBound: 81, upperBound: 121 },
    { week: 'W05', actual: null, forecast: 102, lowerBound: 82, upperBound: 122 },
    { week: 'W06', actual: null, forecast: 105, lowerBound: 84, upperBound: 126 },
    { week: 'W07', actual: null, forecast: 99,  lowerBound: 79, upperBound: 119 },
    { week: 'W08', actual: null, forecast: 110, lowerBound: 88, upperBound: 132 },
    { week: 'W09', actual: null, forecast: 107, lowerBound: 86, upperBound: 128 },
    { week: 'W10', actual: null, forecast: 117, lowerBound: 94, upperBound: 140 },
    { week: 'W11', actual: null, forecast: 120, lowerBound: 96, upperBound: 144 },
    { week: 'W12', actual: null, forecast: 114, lowerBound: 91, upperBound: 137 },
  ],
}

/** @returns {Promise<OverviewData>} */
export async function getOverview({ _runId } = {}) {
  await sleep(450)
  return {
    source: 'mock',
    lastRunId: 'run-003',
    lastRunAt: '2024-11-15T08:00:00Z',
    availableRuns: [
      { runId: 'run-003', label: 'Run #3 — Nov 15, 2024  08:00' },
      { runId: 'run-002', label: 'Run #2 — Nov 13, 2024  14:30' },
      { runId: 'run-001', label: 'Run #1 — Nov 11, 2024  09:15' },
    ],
    planStatus: 'OK',
    // Metrics — values are mock examples; field names proposed, pending backend agreement
    metrics: {
      unmetDemand: { value: 2840,   unit: 'units', delta: -12.3, deltaPositiveIsGood: false },
      expiryLoss:  { value: 45200,  unit: 'USD',   delta: 8.1,   deltaPositiveIsGood: false },
      freightCost: { value: 128400, unit: 'USD',   delta: -3.7,  deltaPositiveIsGood: false },
    },
    riskMix: [
      { name: 'Stockout', value: 28, color: '#7B68F5' },
      { name: 'Expiry',   value: 12, color: '#B5AAF9' },
      { name: 'Excess',   value: 16, color: '#3B3A45' },
    ],
    topAlerts: [
      { alertId: 'alt-01', sku: 'SKU-1042', type: 'Stockout', severity: 'high',   warehouse: 'WH-3', message: 'Projected stockout in 3 weeks' },
      { alertId: 'alt-02', sku: 'SKU-2198', type: 'Expiry',   severity: 'medium', warehouse: 'WH-1', message: '820 units at expiry risk by Dec 2024' },
      { alertId: 'alt-03', sku: 'SKU-0887', type: 'Excess',   severity: 'low',    warehouse: 'WH-5', message: 'Excess stock: 340% of target cover' },
      { alertId: 'alt-04', sku: 'SKU-3341', type: 'Stockout', severity: 'high',   warehouse: 'WH-2', message: 'Projected stockout in 5 weeks' },
      { alertId: 'alt-05', sku: 'SKU-1187', type: 'Expiry',   severity: 'medium', warehouse: 'WH-7', message: '1,240 units at expiry risk by Nov 2024' },
    ],
    pipeline: [
      { step: 'Validate', label: 'Data Validation',  status: 'OK',                completedAt: '2024-11-15T06:00:00Z' },
      { step: 'Forecast', label: 'Demand Forecast',  status: 'FALLBACK_FORECAST', completedAt: '2024-11-15T06:30:00Z' },
      { step: 'Plan',     label: 'Distribution Plan', status: 'OK',               completedAt: '2024-11-15T07:45:00Z' },
      { step: 'Check',    label: 'Plan Check',        status: 'OK',               completedAt: '2024-11-15T07:50:00Z' },
      { step: 'Backtest', label: 'Backtest',          status: 'CHECK_FAILED',      completedAt: '2024-11-15T07:55:00Z' },
    ],
  }
}

/**
 * Demand forecast series — for the overview chart.
 * Accepts { sku } — null means network total.
 * @returns {Promise<{ sku: string, series: DemandPoint[] }>}
 */
export async function getDemandForecast({ sku = null } = {}) {
  await sleep(300)
  const series = (sku && SKU_SERIES[sku]) ? SKU_SERIES[sku] : NETWORK_SERIES
  return {
    source: 'mock',
    sku: sku ?? 'Network total',
    series,
  }
}

/** Available SKU options for the demand chart filter */
export const SKU_OPTIONS = [
  { value: '',         label: 'Network total' },
  { value: 'SKU-1042', label: 'SKU-1042' },
  { value: 'SKU-2198', label: 'SKU-2198' },
]
