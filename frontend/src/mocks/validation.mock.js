import { sleep } from '../lib/utils'

/** @returns {Promise<ValidationReport>} */
export async function getValidationReport() {
  await sleep(400)
  return {
    source: 'mock',
    runId: 'val-003',
    timestamp: '2024-11-15T06:00:00Z',
    // top-level status code
    status: 'OK',
    tablesChecked: 5,
    errorsCount: 0,      // 0 errors → planning is allowed
    warningsCount: 3,    // 3 warnings → warnings-only flow state
    rowsScanned: 45280,
    // inventorySummary intentionally null — not yet exposed by backend
    inventorySummary: null,
    checks: [
      // ── PASS checks ─────────────────────────────────────────────
      {
        id: 'chk-01', name: 'SKU completeness',
        status: 'PASS', severity: 'info',
        message: 'All 340 SKUs present in demand data.',
        table: 'demand', row: null, field: 'sku_id', rule: 'COMPLETENESS_CHECK',
      },
      {
        id: 'chk-02', name: 'Date range continuity',
        status: 'PASS', severity: 'info',
        message: 'No gaps in weekly demand series (52 weeks).',
        table: 'demand', row: null, field: 'week', rule: 'DATE_CONTINUITY',
      },
      {
        id: 'chk-03', name: 'Non-negative inventory',
        status: 'PASS', severity: 'info',
        message: 'All inventory quantities ≥ 0.',
        table: 'inventory', row: null, field: 'qty_on_hand', rule: 'NON_NEGATIVE_CHECK',
      },
      {
        id: 'chk-04', name: 'Warehouse capacity defined',
        status: 'PASS', severity: 'info',
        message: 'All 8 warehouses have capacity limits set.',
        table: 'warehouse_capacity', row: null, field: 'max_capacity', rule: 'REFERENCE_INTEGRITY',
      },
      {
        id: 'chk-05', name: 'Supplier lead times',
        status: 'PASS', severity: 'info',
        message: 'All 62 suppliers have lead-time data.',
        table: 'lead_time', row: null, field: 'lead_days', rule: 'COMPLETENESS_CHECK',
      },
      {
        id: 'chk-06', name: 'SKU–category mapping',
        status: 'PASS', severity: 'info',
        message: 'All SKUs mapped to a product category.',
        table: 'demand', row: null, field: 'category_id', rule: 'REFERENCE_INTEGRITY',
      },
      {
        id: 'chk-07', name: 'Lead-time plausibility',
        status: 'PASS', severity: 'info',
        message: 'All lead times between 1 and 180 days.',
        table: 'lead_time', row: null, field: 'lead_days', rule: 'RANGE_CHECK',
      },
      {
        id: 'chk-08', name: 'Capacity feasibility pre-check',
        status: 'PASS', severity: 'info',
        message: 'Total projected demand does not exceed network capacity.',
        table: 'warehouse_capacity', row: null, field: 'max_capacity', rule: 'FEASIBILITY_PRE_CHECK',
      },
      {
        id: 'chk-09', name: 'Supplier code integrity',
        status: 'PASS', severity: 'info',
        message: 'All demand rows reference valid supplier codes.',
        table: 'demand', row: null, field: 'supplier_id', rule: 'REFERENTIAL_INTEGRITY',
      },
      // ── FAIL / WARNING checks ────────────────────────────────────
      {
        id: 'chk-10', name: 'Demand outlier — SKU-1042',
        status: 'FAIL', severity: 'warning',
        message: 'Demand value 45,230 is 8.2σ above mean for SKU-1042 in week W11. This may skew the forecast significantly.',
        table: 'demand', row: 2847, field: 'demand_qty', rule: 'OUTLIER_Z_SCORE',
      },
      {
        id: 'chk-11', name: 'Zero-demand streak — SKU-2198',
        status: 'FAIL', severity: 'warning',
        message: 'SKU-2198 shows zero demand for 6 consecutive weeks (W03–W08). A possible data gap or product discontinuation.',
        table: 'demand', row: 3102, field: 'demand_qty', rule: 'ZERO_DEMAND_STREAK',
      },
      {
        id: 'chk-12', name: 'Stale inventory snapshot — WH-3',
        status: 'FAIL', severity: 'warning',
        message: 'WH-3 inventory snapshot is 8 days old (threshold: 7 days). Quantities may not reflect current stock.',
        table: 'inventory', row: null, field: 'snapshot_date', rule: 'FRESHNESS_CHECK',
      },
    ],
  }
}

/** @returns {Promise<{ runId: string, queued: boolean }>} */
export async function triggerValidation() {
  await sleep(200)
  return { source: 'mock', runId: 'val-004', queued: true }
}

/** @returns {Promise<{ items: ValidationReport[], total: number }>} */
export async function getValidationHistory({ page = 1, pageSize = 10 } = {}) {
  await sleep(300)
  const STATUS_CYCLE = ['OK', 'OK', 'ERROR_DATA', 'OK']
  return {
    source: 'mock',
    items: Array.from({ length: pageSize }, (_, i) => ({
      runId: `val-${String(i + 1).padStart(3, '0')}`,
      timestamp: new Date(Date.now() - i * 86_400_000).toISOString(),
      status: STATUS_CYCLE[i % STATUS_CYCLE.length],
      tablesChecked: 5,
      checksPassed: 12 - (i % 3),
      checksFailed: i % 3,
    })),
    total: 42,
    page,
    pageSize,
  }
}
