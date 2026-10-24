/**
 * Distribution plan service backed by the synchronous FastAPI planning route.
 */
import { get, post } from './apiClient'
import { DEFAULT_ORIGIN_DATE, ensureDemoData } from './backendApi'
import { exportRun } from './runs'
import * as mock from '../mocks/plan.mock'

const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === 'true'
const PLAN_TIMEOUT_MS = 180_000

function toPlanView(plan) {
  const checker = plan.checker_status ?? plan.checker_verdict ?? {}
  const lines = (plan.plan_lines ?? []).map((line) => ({
    lineId: line.line_id,
    warehouse: line.warehouse_id,
    batchId: line.batch_id,
    sku: line.sku_id,
    description: line.sku_id,
    destination: line.dest_id,
    quantity: line.quantity,
    unit: 'units',
    arrivalDate: line.arrival_date,
    remainingLifeAtArrival: `${line.remaining_life_at_arrival_days} days`,
    freightCost: line.freight_cost,
    explanation: line.explanation?.sentence ?? '',
    status: checker.passed ? 'OK' : 'CHECK_FAILED',
  }))
  const summary = plan.summary ?? {}
  const deltaPercent = (before, after) => (
    before > 0 ? ((after - before) / before) * 100 : null
  )
  const warehouseTotals = Object.values(lines.reduce((groups, line) => {
    const group = groups[line.warehouse] ??= {
      warehouse: line.warehouse,
      shipments: 0,
      quantity: 0,
    }
    group.shipments += 1
    group.quantity += line.quantity
    return groups
  }, {}))
  const destinationTotals = Object.values(lines.reduce((groups, line) => {
    const group = groups[line.destination] ??= {
      name: line.destination,
      shipments: 0,
      value: 0,
      color: '#7B68F5',
    }
    group.shipments += 1
    group.value += line.quantity
    return groups
  }, {}))
  const status = !checker.passed
    ? 'CHECK_FAILED'
    : plan.solver_status === 'OPTIMAL'
      ? 'OK'
      : plan.solver_status ?? plan.status

  return {
    source: 'api',
    runId: plan.run_id,
    originDate: plan.origin_date,
    status,
    statusMessage: `Solver: ${plan.solver_status ?? 'unknown'}; independent verification ${checker.passed ? 'passed' : 'failed'}.`,
    lines,
    beforeAfterMetrics: {
      unmetDemand: {
        before: summary.expected_unmet_demand_before,
        after: summary.expected_unmet_demand_after,
        deltaPercent: deltaPercent(
          summary.expected_unmet_demand_before,
          summary.expected_unmet_demand_after
        ),
      },
      expiryLoss: {
        before: summary.expected_expiry_loss_before,
        after: summary.expected_expiry_loss_after,
        deltaPercent: deltaPercent(
          summary.expected_expiry_loss_before,
          summary.expected_expiry_loss_after
        ),
      },
      freightCost: { after: summary.total_freight_cost },
      independentChecker: {
        status: checker.passed ? 'PASSED' : 'FAILED',
        violationsCount: checker.violations_count ?? checker.violations?.length ?? 0,
        message: checker.passed
          ? 'All independent plan checks passed.'
          : 'Independent verification rejected this plan.',
      },
    },
    warehouseShipments: warehouseTotals,
    destinationRegionShipments: destinationTotals,
  }
}

async function createPlan(params = {}) {
  await ensureDemoData()
  const response = await post('/plan', {
    timeout: PLAN_TIMEOUT_MS,
    body: {
      origin_date: params.dispatchDate ?? params.originDate ?? DEFAULT_ORIGIN_DATE,
      horizon_days: params.horizonDays ?? 7,
      lane_pruning_k: params.lanePruningK ?? 3,
      dataset_path: params.datasetPath,
    },
  })
  return toPlanView(response)
}

export async function getDistributionPlan(params = {}) {
  if (USE_MOCKS) return mock.getDistributionPlan(params)
  await ensureDemoData()
  const runId = params.runId
  if (runId) {
    return toPlanView(await get(`/runs/${encodeURIComponent(runId)}`))
  }
  const runs = await get('/runs')
  const latestPlan = runs.find((run) => run.run_type === 'PLAN')
  if (latestPlan) {
    return toPlanView(await get(`/runs/${encodeURIComponent(latestPlan.run_id)}`))
  }
  return createPlan(params)
}

export async function getPlanLine({ lineId } = {}) {
  if (USE_MOCKS) return mock.getPlanLine({ lineId })
  await ensureDemoData()
  const runs = await get('/runs')
  for (const run of runs.filter((item) => item.run_type === 'PLAN')) {
    const manifest = await get(`/runs/${encodeURIComponent(run.run_id)}`)
    const line = manifest.plan_lines?.find((item) => item.line_id === lineId)
    if (line) {
      const view = toPlanView(manifest)
      const currentIndex = view.lines.findIndex((item) => item.lineId === lineId)
      const evidence = line.explanation?.evidence ?? {}
      const forecastRange = evidence.forecast_range ?? []
      return {
        ...view.lines[currentIndex],
        navigation: {
          currentIndex: currentIndex + 1,
          totalLines: view.lines.length,
          previousLineId: view.lines[currentIndex - 1]?.lineId ?? null,
          nextLineId: view.lines[currentIndex + 1]?.lineId ?? null,
        },
        explanationVerified: manifest.checker_verdict?.passed ?? false,
        forecastEvidence: [{
          period: 'Forecast horizon',
          low: forecastRange[0],
          mid: evidence.forecast_mean,
          high: forecastRange[1],
        }],
        stockEvidence: {
          currentDestinationStock: evidence.current_stock,
          inboundDestination: evidence.inbound_stock,
          shippedQuantity: evidence.shipped_quantity,
        },
        shelfLifeEvidence: {
          remainingAtArrivalDays: evidence.remaining_shelf_life_arrival,
          skuMinimumDays: evidence.min_life_requirement,
        },
        nextBestAlternative: evidence.next_best_warehouse
          ? {
              warehouse: evidence.next_best_warehouse,
              cost: evidence.freight_cost_next_best,
              selectedCost: evidence.freight_cost_selected,
            }
          : null,
        evidence,
      }
    }
  }
  return null
}

export async function triggerPlan(params = {}) {
  if (USE_MOCKS) return mock.triggerPlan(params)
  return createPlan(params)
}

export async function generatePlanWithProgress({
  dispatchDate,
  onProgress,
} = {}) {
  onProgress?.('Submitting the planning request to the solver...', 10)
  const plan = await triggerPlan({ dispatchDate })
  onProgress?.('Independent verification completed.', 100)
  return plan
}

export async function exportDistributionPlan(runId) {
  return exportRun({ runId, format: 'csv', artifact: 'plan' })
}
