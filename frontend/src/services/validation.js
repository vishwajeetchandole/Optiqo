/**
 * Data validation service backed by the FastAPI validation contract.
 */
import { post } from './apiClient'
import { DEFAULT_ORIGIN_DATE, ensureDemoData } from './backendApi'
import * as mock from '../mocks/validation.mock'

const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === 'true'

function toValidationReport(report) {
  const findings = [
    ...(report.errors ?? []).map((item) => ({ ...item, findingType: 'error' })),
    ...(report.warnings ?? []).map((item) => ({ ...item, findingType: 'warning' })),
  ]
  return {
    source: 'api',
    timestamp: report.summary.checked_at,
    status: report.status,
    planningBlocked: report.planning_blocked,
    tablesChecked: report.summary.total_tables_checked,
    errorsCount: report.error_count,
    warningsCount: report.warning_count,
    checks: findings.map((item, index) => ({
      id: `${item.findingType}-${item.table}-${item.row_index ?? 'table'}-${index}`,
      name: `${item.findingType === 'error' ? 'Error' : 'Warning'}: ${item.rule}`,
      status: 'FAIL',
      severity: item.findingType === 'error' ? 'critical' : 'warning',
      message: item.message,
      table: item.table,
      row: item.row_index,
      field: item.field,
      rule: item.rule,
      observedValue: item.observed_value,
    })),
  }
}

export async function getValidationReport() {
  if (USE_MOCKS) return mock.getValidationReport()
  await ensureDemoData()
  const report = await post('/data/validate', {
    body: { planning_date: DEFAULT_ORIGIN_DATE },
  })
  return toValidationReport(report)
}

export async function triggerValidation(params = {}) {
  if (USE_MOCKS) return mock.triggerValidation(params)
  await ensureDemoData()
  const report = await post('/data/validate', {
    body: {
      planning_date: params.planningDate ?? DEFAULT_ORIGIN_DATE,
      dataset_path: params.datasetPath,
      exclude_expired_batches: params.excludeExpiredBatches ?? true,
    },
  })
  return toValidationReport(report)
}

export async function getValidationHistory(params = {}) {
  if (USE_MOCKS) return mock.getValidationHistory(params)
  return { items: [], total: 0, page: params.page ?? 1, pageSize: params.pageSize ?? 10 }
}
