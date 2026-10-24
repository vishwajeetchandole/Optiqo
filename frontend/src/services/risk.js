/**
 * Risk service backed by the FastAPI risk contract.
 */
import { get } from './apiClient'
import { DEFAULT_ORIGIN_DATE, ensureDemoData } from './backendApi'
import * as mock from '../mocks/risk.mock'

const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === 'true'

function classifyRisk(alert) {
  const driver = alert.primary_driver.toLowerCase()
  if (driver.includes('expir')) return 'Expiry'
  if (driver.includes('excess')) return 'Excess'
  return 'Stockout'
}

function toRiskOverview(response) {
  const rankedPairs = response.alerts.map((alert, index) => ({
    rank: index + 1,
    pairId: `${alert.dest_id}-${alert.sku_id}`,
    sku: alert.sku_id,
    productName: alert.sku_id,
    destination: alert.dest_id,
    region: 'Not provided',
    daysOfCover: alert.days_of_cover,
    expectedUnmetDemand: alert.expected_unmet_units,
    expectedExpiryLoss: alert.expected_expiry_loss_cost,
    riskType: classifyRisk(alert),
    severity: alert.severity.toLowerCase(),
    drivers: { primaryDriver: alert.primary_driver },
    rationale: alert.primary_driver,
  }))

  const byRiskType = rankedPairs.reduce((counts, alert) => {
    counts[alert.riskType] = (counts[alert.riskType] ?? 0) + 1
    return counts
  }, {})
  const severityCounts = rankedPairs.reduce((counts, alert) => {
    counts[alert.severity] = (counts[alert.severity] ?? 0) + 1
    return counts
  }, {})

  return {
    source: 'api',
    originDate: response.origin_date,
    runId: response.run_id ?? null,
    rankedPairs,
    summaryCards: {
      totalAlerts: response.total_alerts,
      critical: severityCounts.critical ?? 0,
      high: response.high_severity_count,
      medium: response.medium_severity_count,
      low: response.low_severity_count,
    },
    networkShortages: (response.supply_shortage_skus ?? []).map((sku) => ({
      shortageId: sku,
      sku,
    })),
    riskCounts: byRiskType,
  }
}

export async function getRiskOverview(params = {}) {
  if (USE_MOCKS) return mock.getRiskOverview()
  await ensureDemoData()
  const response = await get('/risk', {
    query: {
      origin_date: params.originDate ?? DEFAULT_ORIGIN_DATE,
      dataset_path: params.datasetPath,
      run_id: params.runId,
    },
  })
  return toRiskOverview(response)
}

export async function getRiskBreakdown(params = {}) {
  if (USE_MOCKS) return mock.getRiskBreakdown(params)
  const overview = await getRiskOverview(params)
  return overview.rankedPairs.filter((item) => !params.category || item.riskType === params.category)
}

export async function getTopAlerts(params = {}) {
  if (USE_MOCKS) return mock.getTopAlerts(params)
  const overview = await getRiskOverview(params)
  return overview.rankedPairs.slice(0, Math.max(1, Number(params.limit) || 10))
}
