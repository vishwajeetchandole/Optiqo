import { formatInr, sleep } from '../lib/utils'

/**
 * Plan mock with realistic lines, before/after metrics,
 * warehouse & destination charts, and full support for all 7 PRD status codes.
 * Source tagged as "mock".
 */

export const MOCK_PLAN_LINES = [
  {
    lineId: 'line-001',
    warehouse: 'WH-1 (Newark DC)',
    batchId: 'BAT-9024',
    sku: 'SKU-1042',
    description: 'Cold-Chain Vaccine Pack',
    destination: 'WH-3 (Chicago DC)',
    quantity: 1450,
    unit: 'units',
    arrivalDate: '2024-11-19',
    remainingLifeAtArrival: '180 days',
    freightCost: 3420,
    region: 'North America',
    status: 'OK',
    priority: 'high',
  },
  {
    lineId: 'line-002',
    warehouse: 'WH-1 (Newark DC)',
    batchId: 'BAT-8812',
    sku: 'SKU-2198',
    description: 'Oncology Adjuvant Monoclonal',
    destination: 'WH-5 (Dallas DC)',
    quantity: 820,
    unit: 'units',
    arrivalDate: '2024-11-20',
    remainingLifeAtArrival: '45 days',
    freightCost: 2850,
    region: 'North America',
    status: 'OK',
    priority: 'high',
  },
  {
    lineId: 'line-003',
    warehouse: 'WH-4 (Rotterdam DC)',
    batchId: 'BAT-7740',
    sku: 'SKU-3341',
    description: 'Lyophilized Injectable Buffer',
    destination: 'WH-2 (Frankfurt DC)',
    quantity: 2400,
    unit: 'units',
    arrivalDate: '2024-11-18',
    remainingLifeAtArrival: '210 days',
    freightCost: 1940,
    region: 'EMEA',
    status: 'OK',
    priority: 'high',
  },
  {
    lineId: 'line-004',
    warehouse: 'WH-4 (Rotterdam DC)',
    batchId: 'BAT-6102',
    sku: 'SKU-5421',
    description: 'Sterile Saline IV Infusion',
    destination: 'WH-2 (Frankfurt DC)',
    quantity: 3600,
    unit: 'units',
    arrivalDate: '2024-11-18',
    remainingLifeAtArrival: '340 days',
    freightCost: 2100,
    region: 'EMEA',
    status: 'OK',
    priority: 'medium',
  },
  {
    lineId: 'line-005',
    warehouse: 'WH-3 (Chicago DC)',
    batchId: 'BAT-5021',
    sku: 'SKU-0887',
    description: 'Pediatric Antibiotic Suspension',
    destination: 'WH-5 (Dallas DC)',
    quantity: 1200,
    unit: 'units',
    arrivalDate: '2024-11-21',
    remainingLifeAtArrival: '90 days',
    freightCost: 1850,
    region: 'North America',
    status: 'OK',
    priority: 'medium',
  },
  {
    lineId: 'line-006',
    warehouse: 'WH-7 (Singapore DC)',
    batchId: 'BAT-4419',
    sku: 'SKU-6102',
    description: 'Biologic Syringe Auto-Injector',
    destination: 'WH-6 (Tokyo DC)',
    quantity: 980,
    unit: 'units',
    arrivalDate: '2024-11-22',
    remainingLifeAtArrival: '140 days',
    freightCost: 4600,
    region: 'APAC',
    status: 'OK',
    priority: 'high',
  },
  {
    lineId: 'line-007',
    warehouse: 'WH-7 (Singapore DC)',
    batchId: 'BAT-3920',
    sku: 'SKU-1187',
    description: 'Insulin Glargine Multi-Dose',
    destination: 'WH-6 (Tokyo DC)',
    quantity: 1100,
    unit: 'units',
    arrivalDate: '2024-11-22',
    remainingLifeAtArrival: '60 days',
    freightCost: 3900,
    region: 'APAC',
    status: 'OK',
    priority: 'medium',
  },
  {
    lineId: 'line-008',
    warehouse: 'WH-5 (Dallas DC)',
    batchId: 'BAT-9104',
    sku: 'SKU-7729',
    description: 'Cardiovascular Heparin Infusion',
    destination: 'WH-8 (Sao Paulo DC)',
    quantity: 820,
    unit: 'units',
    arrivalDate: '2024-11-25',
    remainingLifeAtArrival: '120 days',
    freightCost: 5800,
    region: 'LATAM',
    status: 'OK',
    priority: 'high',
  },
  {
    lineId: 'line-009',
    warehouse: 'WH-2 (Frankfurt DC)',
    batchId: 'BAT-2041',
    sku: 'SKU-4412',
    description: 'Diagnostic Assay Reagent Kit',
    destination: 'WH-4 (Rotterdam DC)',
    quantity: 650,
    unit: 'units',
    arrivalDate: '2024-11-19',
    remainingLifeAtArrival: '50 days',
    freightCost: 1450,
    region: 'EMEA',
    status: 'OK',
    priority: 'medium',
  },
  {
    lineId: 'line-010',
    warehouse: 'WH-1 (Newark DC)',
    batchId: 'BAT-1102',
    sku: 'SKU-8821',
    description: 'Surgical Antimicrobial Film',
    destination: 'WH-3 (Chicago DC)',
    quantity: 1800,
    unit: 'units',
    arrivalDate: '2024-11-20',
    remainingLifeAtArrival: '300 days',
    freightCost: 2200,
    region: 'North America',
    status: 'OK',
    priority: 'low',
  },
  {
    lineId: 'line-011',
    warehouse: 'WH-3 (Chicago DC)',
    batchId: 'BAT-6502',
    sku: 'SKU-9014',
    description: 'Ophthalmic Lubricant Solution',
    destination: 'WH-1 (Newark DC)',
    quantity: 750,
    unit: 'units',
    arrivalDate: '2024-11-21',
    remainingLifeAtArrival: '200 days',
    freightCost: 1650,
    region: 'North America',
    status: 'OK',
    priority: 'low',
  },
  {
    lineId: 'line-012',
    warehouse: 'WH-5 (Dallas DC)',
    batchId: 'BAT-8219',
    sku: 'SKU-3129',
    description: 'Enteral Nutrition Formula 500ml',
    destination: 'WH-8 (Sao Paulo DC)',
    quantity: 1200,
    unit: 'units',
    arrivalDate: '2024-11-26',
    remainingLifeAtArrival: '60 days',
    freightCost: 6100,
    region: 'LATAM',
    status: 'OK',
    priority: 'medium',
  },
]

export const MOCK_WAREHOUSE_SHIPMENTS = [
  { warehouse: 'WH-1 (Newark)', shipments: 3, quantity: 4070 },
  { warehouse: 'WH-4 (Rotterdam)', shipments: 2, quantity: 6000 },
  { warehouse: 'WH-3 (Chicago)', shipments: 2, quantity: 1950 },
  { warehouse: 'WH-7 (Singapore)', shipments: 2, quantity: 2080 },
  { warehouse: 'WH-5 (Dallas)', shipments: 2, quantity: 2020 },
  { warehouse: 'WH-2 (Frankfurt)', shipments: 1, quantity: 650 },
]

export const MOCK_DESTINATION_REGION_SHIPMENTS = [
  { name: 'North America', value: 5870, color: '#7B68F5' },
  { name: 'EMEA',          value: 6650, color: '#3B82F6' },
  { name: 'APAC',          value: 2080, color: '#10B981' },
  { name: 'LATAM',         value: 2020, color: '#F59E0B' },
]

const STATUS_MESSAGES = {
  OK: 'Optimal distribution plan generated successfully within convergence tolerance.',
  FALLBACK_FORECAST: 'Plan generated using moving-average fallback forecast because Holt-Winters model failed stationarity tests for 2 SKUs.',
  SOLVER_TIMEOUT: 'Solver reached the 60.0s execution timeout budget. Returning best-found feasible incumbent solution (optimality gap 3.8%).',
  SOLVER_NOT_OPTIMAL: 'Solver terminated early with a feasible solution, but the optimality gap exceeds the 1.0% tolerance.',
  INFEASIBLE: 'No feasible plan exists. Constraint conflict between warehouse capacity limits at WH-3 and minimum safety cover requirements for SKU-1042.',
  CHECK_FAILED: 'Post-solve independent constraint verification failed: 2 physical invariant violations detected (negative stock projection at WH-2).',
  ERROR_DATA: 'Solver input data contains critical integrity errors (unresolved foreign keys in demand matrix).',
}

/**
 * Fetch the active distribution plan
 * @param {{ runId?: string, statusOverride?: string }} params
 */
export async function getDistributionPlan({ statusOverride = 'OK' } = {}) {
  await sleep(400)

  const status = statusOverride
  const isFinal = status === 'OK' || status === 'FALLBACK_FORECAST'

  return {
    source: 'mock',
    runId: 'plan-003',
    timestamp: '2024-11-15T08:00:00Z',
    dispatchDate: '2024-11-16',
    status,
    statusMessage: STATUS_MESSAGES[status] ?? 'Solver completed.',
    solverDurationMs: 4200,
    isFinal,
    beforeAfterMetrics: {
      unmetDemand: {
        before: 8420,
        after: isFinal ? 1200 : 8420,
        unit: 'units',
        deltaPercent: isFinal ? -85.7 : 0,
      },
      expiryLoss: {
        before: 86400,
        after: isFinal ? 18200 : 86400,
        unit: 'USD',
        deltaPercent: isFinal ? -78.9 : 0,
      },
      freightCost: {
        before: 0,
        after: isFinal ? 37910 : 0,
        unit: 'USD',
        deltaPercent: null,
      },
      independentChecker: {
        status: status === 'CHECK_FAILED' ? 'FAILED' : 'PASSED',
        violationsCount: status === 'CHECK_FAILED' ? 2 : 0,
        rulesChecked: 18,
        message:
          status === 'CHECK_FAILED'
            ? '2 invariant violations detected in independent check.'
            : 'All 18 hard physical invariants verified independently (capacity, shelf-life, non-negativity).',
      },
    },
    lines: isFinal ? MOCK_PLAN_LINES : [],
    totalLines: isFinal ? MOCK_PLAN_LINES.length : 0,
    warehouseShipments: MOCK_WAREHOUSE_SHIPMENTS,
    destinationRegionShipments: MOCK_DESTINATION_REGION_SHIPMENTS,
  }
}

/**
 * Single plan line detail (PRD J4 / P0-08 Recommendation Detail)
 */
export async function getPlanLine({ lineId } = {}) {
  await sleep(250)
  const index = MOCK_PLAN_LINES.findIndex((l) => l.lineId === lineId)
  if (index === -1) {
    // Return null for unknown lineId to allow graceful 404
    return null
  }

  const line = MOCK_PLAN_LINES[index]
  const prevLine = index > 0 ? MOCK_PLAN_LINES[index - 1] : null
  const nextLine = index < MOCK_PLAN_LINES.length - 1 ? MOCK_PLAN_LINES[index + 1] : null

  return {
    source: 'mock',
    ...line,
    // One-sentence explanation as supplied by the backend (PRD P0-08)
    explanation: `Dispatch of ${line.quantity} units from ${line.warehouse} to ${line.destination} resolves projected stockout on ${line.arrivalDate} while maintaining a 135-day safety margin over the 45-day clinical shelf-life threshold.`,
    explanationVerified: true,
    verifierRuleId: 'PRD-P0-08-INVARIANT-VERIFIED',
    verifierTimestamp: '2024-11-15T08:00:04Z',
    forecastEvidence: [
      { period: 'W45', low: Math.round(line.quantity * 0.75), mid: Math.round(line.quantity * 0.9), high: Math.round(line.quantity * 1.1) },
      { period: 'W46 (Arrival)', low: Math.round(line.quantity * 0.85), mid: line.quantity, high: Math.round(line.quantity * 1.2) },
      { period: 'W47', low: Math.round(line.quantity * 0.8), mid: Math.round(line.quantity * 0.95), high: Math.round(line.quantity * 1.15) },
      { period: 'W48', low: Math.round(line.quantity * 0.85), mid: Math.round(line.quantity * 1.05), high: Math.round(line.quantity * 1.25) },
    ],
    stockEvidence: {
      currentOriginStock: 4200,
      inboundDestination: 140,
      selectedTransferQty: line.quantity,
      projectedDestinationBalance: 140 + line.quantity,
      unit: line.unit,
    },
    shelfLifeEvidence: {
      remainingAtArrivalDays: 180,
      skuMinimumDays: 45,
      totalShelfLifeDays: 240,
      ratioPercent: 75,
      status: 'MET',
    },
    nextBestAlternative: {
      warehouse: 'WH-5 (Dallas DC)',
      batchId: 'BAT-7712',
      cost: line.freightCost + 1820,
      extraCost: 1820,
      transitDays: 4,
      eligible: true,
      reasonNotChosen: `Higher freight cost (${formatInr(line.freightCost + 1820)} vs ${formatInr(line.freightCost)}) and 24h longer transit time.`,
    },
    bindingConstraints: [
      'Origin Cold Storage Capacity (92% utilization limit)',
      'Clinical Shelf-Life Threshold (≥ 45 days at destination)',
      'Lead-Time Delivery Feasibility (≤ 72h transit window)',
    ],
    navigation: {
      previousLineId: prevLine?.lineId || null,
      nextLineId: nextLine?.lineId || null,
      totalLines: MOCK_PLAN_LINES.length,
      currentIndex: index + 1,
    },
  }
}

/**
 * Trigger plan generation with simulated staged progress
 */
export async function triggerPlan(_params = {}) {
  await sleep(300)
  return {
    source: 'mock',
    runId: 'plan-004',
    status: 'QUEUED',
    queued: true,
  }
}
