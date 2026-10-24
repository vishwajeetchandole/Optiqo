/**
 * Backtesting service backed by the FastAPI simulation and run-storage routes.
 */
import { get, post } from './apiClient'
import { ensureDemoData } from './backendApi'
import * as mock from '../mocks/backtest.mock'

const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === 'true'
const BACKTEST_TIMEOUT_MS = 300_000

const KPI_DEFINITIONS = [
  ['K1', 'Unmet Demand Rate', '%', 'relative_reduction_vs_b1_pct'],
  ['K2', 'Fill Rate', '%', 'target_met'],
  ['K3', 'Stockout Days Rate', '%', 'relative_reduction_vs_b1_pct'],
  ['K4', 'Expiry Wastage', 'units', 'relative_reduction_vs_b1_pct'],
  ['K5', 'Total Freight Cost', 'cost units', 'relative_reduction_per_unit_pct'],
  ['K6', 'Total Modeled Cost', 'cost units', 'relative_reduction_vs_b1_pct'],
  ['K7', 'Ending Inventory', 'units', 'percentage_above_b1'],
]

function percentDifference(base, value, higherIsBetter = false) {
  if (!Number.isFinite(base) || Math.abs(base) < 1e-9) return 0
  return Number((((higherIsBetter ? value - base : base - value) / Math.abs(base)) * 100).toFixed(1))
}

function toBacktestView(result, metadata = {}) {
  const comparison = result.kpi_comparison
  if (!comparison) return null

  const values = [
    comparison.unmet_demand_rate_k1,
    comparison.fill_rate_k2,
    comparison.stockout_days_rate_k3,
    comparison.expiry_wastage_units_k4,
    comparison.total_freight_cost_k5,
    comparison.total_modeled_cost_k6,
    comparison.ending_inventory_units_k7,
  ]
  const kpis = values.map((item, index) => {
    const [id, name, unit] = KPI_DEFINITIONS[index]
    const scale = unit === '%' ? 100 : 1
    const b1 = item.b1 * scale
    const b2 = item.b2 * scale
    const optiqo = item.optiqo * scale
    const higherIsBetter = id === 'K2'
    const relative = id === 'K1'
      ? item.relative_reduction_vs_b2_pct
      : id === 'K2'
        ? percentDifference(b2, optiqo, true)
        : id === 'K5'
          ? percentDifference(b2, optiqo)
          : id === 'K7'
            ? null
            : percentDifference(b2, optiqo)
    const thresholdMet = id === 'K1'
      ? item.target_met_vs_b1
      : id === 'K2'
        ? item.target_met
        : null
    const b2Beat = id === 'K7'
      ? null
      : (higherIsBetter ? optiqo >= b2 : optiqo <= b2)
    return {
      id,
      name,
      unit,
      threshold: thresholdMet == null ? 'Not defined' : 'Backend target',
      b1,
      b2,
      optiqo,
      diffVsB2Abs: Number((optiqo - b2).toFixed(3)),
      diffVsB2Rel: relative,
      b2BeatStatus: b2Beat == null ? 'NOT_EVALUATED' : b2Beat ? 'MET' : 'NOT_MET',
      thresholdStatus: thresholdMet == null
        ? 'NOT_EVALUATED'
        : thresholdMet ? 'MET' : 'NOT_MET',
    }
  })

  const costs = comparison.gain_decomposition_k8.total_modeled_cost
  const windowDays = result.window_days ?? metadata.parameters?.window_days
  return {
    source: 'api',
    runId: result.run_id ?? metadata.run_id,
    timestamp: result.created_at ?? metadata.created_at,
    seed: result.seed ?? metadata.seed ?? null,
    evaluationWindow: windowDays == null ? '—' : `${windowDays} days`,
    systemMetadata: {
      dataset: result.dataset_hash ?? metadata.dataset_hash ?? 'Dataset unavailable',
      solverVersion: result.software_versions?.optiqo ?? 'Backend engine',
      underlyingMip: result.software_versions?.pulp ?? 'PuLP',
    },
    kpis,
    gainDecomposition: [
      {
        name: 'Forecast Effect (B1→B2)',
        value: -costs.forecast_effect_b1_to_b2,
        baseline: 0,
      },
      {
        name: 'Allocation Effect (B2→Optiqo)',
        value: -costs.allocation_effect_b2_to_optiqo,
        baseline: 0,
      },
    ],
    dailyMetrics: [],
    forecastKpis: result.forecast_kpis,
    optimizationKpis: result.optimization_kpis,
  }
}

function toWindowDays(window) {
  const weeks = Number.parseInt(String(window ?? '8w').replace(/w$/, ''), 10)
  if (!Number.isFinite(weeks)) return 56
  return Math.min(112, Math.max(7, weeks * 7))
}

export async function getBacktestSummary() {
  if (USE_MOCKS) return mock.getBacktestSummary()
  const runs = await get('/runs')
  const latest = runs.find((run) => run.run_type === 'BACKTEST')
  if (!latest) return null
  const manifest = await get(`/runs/${encodeURIComponent(latest.run_id)}`)
  return toBacktestView(manifest, latest)
}

export async function getBacktestHistory({ page = 1, pageSize = 10 } = {}) {
  if (USE_MOCKS) return mock.getBacktestHistory({ page, pageSize })
  const runs = await get('/runs')
  const backtests = runs
    .filter((run) => run.run_type === 'BACKTEST')
    .slice((page - 1) * pageSize, page * pageSize)
    .map((run) => ({
      runId: run.run_id,
      timestamp: run.created_at,
      status: run.status,
      seed: run.seed ?? null,
      window: run.parameters?.window_days ? `${run.parameters.window_days}d` : '—',
    }))
  return { source: 'api', items: backtests, total: runs.filter((run) => run.run_type === 'BACKTEST').length, page, pageSize }
}

export async function triggerBacktest(config = {}) {
  if (USE_MOCKS) return mock.triggerBacktest(config)
  const seed = Number(config.seed ?? 42)
  await ensureDemoData(seed)
  const result = await post('/backtest', {
    timeout: BACKTEST_TIMEOUT_MS,
    body: {
      seed,
      window_days: toWindowDays(config.window),
      evaluation_start_date: config.evaluationStartDate,
    },
  })
  const manifest = await get(`/runs/${encodeURIComponent(result.run_id)}`)
  return toBacktestView(manifest, result)
}

export async function runBacktestWithProgress({
  window = '8w',
  seed = 42,
  onProgress,
} = {}) {
  onProgress?.('Running the requested policy comparison and KPI evaluation...', 10)
  const result = await triggerBacktest({ window, seed })
  onProgress?.('Backtest completed and metrics were persisted.', 100)
  return result
}
