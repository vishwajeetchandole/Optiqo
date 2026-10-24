/**
 * Overview service aggregates data from the available backend contracts.
 */
import { get } from './apiClient'
import { DEFAULT_ORIGIN_DATE, ensureDemoData } from './backendApi'
import { getRiskOverview } from './risk'
import * as mock from '../mocks/overview.mock'

const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === 'true'

export async function getOverview() {
  if (USE_MOCKS) return mock.getOverview()
  await ensureDemoData()
  const [risk, storedRuns] = await Promise.all([
    getRiskOverview({ originDate: DEFAULT_ORIGIN_DATE }),
    get('/runs'),
  ])

  const planRuns = storedRuns.filter((run) => run.run_type === 'PLAN')
  const latestRun = planRuns[0] ?? null
  const latestManifest = latestRun
    ? await get(`/runs/${encodeURIComponent(latestRun.run_id)}`)
    : null
  const alerts = risk.rankedPairs
  const riskCounts = alerts.reduce((counts, alert) => {
    counts[alert.riskType] = (counts[alert.riskType] ?? 0) + 1
    return counts
  }, {})

  return {
    source: 'api',
    lastRunId: latestRun?.run_id ?? null,
    lastRunAt: latestRun?.created_at ?? null,
    availableRuns: planRuns.map((run) => ({
      runId: run.run_id,
      label: `${run.run_id} — ${run.created_at ?? 'date unavailable'}`,
    })),
    planStatus: latestRun?.status ?? 'NOT_RUN',
    metrics: {
      unmetDemand: {
        value: alerts.reduce((sum, alert) => sum + alert.expectedUnmetDemand, 0),
        unit: 'units',
        delta: null,
        deltaPositiveIsGood: false,
      },
      expiryLoss: {
        value: alerts.reduce((sum, alert) => sum + alert.expectedExpiryLoss, 0),
        unit: 'cost units',
        delta: null,
        deltaPositiveIsGood: false,
      },
      freightCost: {
        value: latestManifest?.summary?.total_freight_cost ?? null,
        unit: 'cost units',
        delta: null,
        deltaPositiveIsGood: false,
      },
    },
    riskMix: [
      { name: 'Stockout', value: riskCounts.Stockout ?? 0, color: '#7B68F5' },
      { name: 'Expiry', value: riskCounts.Expiry ?? 0, color: '#B5AAF9' },
      { name: 'Excess', value: riskCounts.Excess ?? 0, color: '#3B3A45' },
    ],
    topAlerts: alerts.slice(0, 5).map((alert) => ({
      alertId: alert.pairId,
      sku: alert.sku,
      type: alert.riskType,
      severity: alert.severity,
      warehouse: alert.destination,
      message: alert.rationale,
    })),
    pipeline: [
      { step: 'Validate', status: 'NOT_RUN' },
      { step: 'Forecast', status: 'NOT_RUN' },
      { step: 'Plan', status: latestRun?.status ?? 'NOT_RUN' },
      {
        step: 'Check',
        status: latestManifest?.checker_verdict?.passed ? 'OK' : 'NOT_RUN',
      },
      {
        step: 'Backtest',
        status: storedRuns.some((run) => run.run_type === 'BACKTEST') ? 'OK' : 'NOT_RUN',
      },
    ],
  }
}

export async function getDemandForecast(params = {}) {
  if (USE_MOCKS) return mock.getDemandForecast(params)
  const { getForecastSeries } = await import('./forecast')
  return getForecastSeries({
    sku: params.sku,
    horizon: 7,
    originDate: params.originDate ?? DEFAULT_ORIGIN_DATE,
  })
}

export const SKU_OPTIONS = [
  { value: '', label: 'Network total' },
  ...Array.from({ length: 30 }, (_, index) => {
    const value = `SKU_${String(index + 1).padStart(3, '0')}`
    return { value, label: value }
  }),
]
