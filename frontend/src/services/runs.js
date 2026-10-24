/**
 * Run history and export services backed by FastAPI.
 */
import { get } from './apiClient'
import { MOCK_PLAN_LINES } from '../mocks/plan.mock'
import * as mock from '../mocks/runs.mock'

const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === 'true'

function toRunView(run) {
  const manifest = run.manifest ?? run
  const parameters = manifest.parameters ?? {}
  const planLines = manifest.plan_lines ?? []
  return {
    ...manifest,
    source: 'api',
    runId: manifest.run_id,
    timestamp: manifest.created_at,
    dataset: manifest.dataset_hash ? `sha256:${manifest.dataset_hash}` : 'Dataset unavailable',
    isSimulated: false,
    seed: manifest.seed ?? parameters.seed ?? null,
    planLinesCount: planLines.length,
    durationMs: manifest.solver_runtime_seconds == null
      ? null
      : Math.round(manifest.solver_runtime_seconds * 1000),
    solverStatusMessage: manifest.solver_status ?? manifest.status,
    manifest: {
      ...manifest,
      datasetHash: manifest.dataset_hash,
      libraryVersions: manifest.software_versions ?? {},
    },
  }
}

export async function getRuns({ page = 1, pageSize = 10, status } = {}) {
  if (USE_MOCKS) return mock.getRuns({ page, pageSize, status })
  const records = await get('/runs')
  const all = records.map((run) => toRunView(run))
  const filtered = status && status !== 'ALL'
    ? all.filter((run) => run.status === status)
    : all
  return {
    source: 'api',
    items: filtered.slice((page - 1) * pageSize, page * pageSize),
    total: filtered.length,
    page,
    pageSize,
  }
}

export async function getRun({ runId } = {}) {
  if (USE_MOCKS) return mock.getRun({ runId })
  const manifest = await get(`/runs/${encodeURIComponent(runId)}`)
  return toRunView(manifest)
}

export async function exportRun({ runId, format = 'csv', artifact = 'plan' } = {}) {
  if (USE_MOCKS) {
    if (format === 'csv' && artifact === 'plan') {
      const headers = ['Line ID', 'Origin Warehouse', 'Batch ID', 'SKU', 'Destination', 'Quantity', 'Arrival Date', 'Remaining Life', 'Freight Cost']
      const escape = (value) => {
        const text = value == null ? '' : String(value)
        const safe = /^[=+\-@\t\r]/.test(text) ? `'${text}` : text
        return `"${safe.replaceAll('"', '""')}"`
      }
      const rows = MOCK_PLAN_LINES.map((line) => [
        line.lineId,
        line.warehouse,
        line.batchId,
        line.sku,
        line.destination,
        line.quantity,
        line.arrivalDate,
        line.remainingLifeAtArrival,
        line.freightCost,
      ])
      return {
        source: 'mock',
        runId,
        format,
        artifact,
        filename: `optiqo_${runId}_plan.csv`,
        blob: new Blob([
          [headers, ...rows].map((row) => row.map(escape).join(',')).join('\r\n'),
        ], { type: 'text/csv;charset=utf-8' }),
      }
    }
    return mock.exportRun({ runId, format, artifact })
  }
  const content = await get(`/runs/${encodeURIComponent(runId)}/export`, {
    query: { format, artifact },
  })
  return {
    source: 'api',
    runId,
    format,
    artifact,
    filename: `${runId}_${artifact}.${format}`,
    blob: new Blob([typeof content === 'string' ? content : JSON.stringify(content)], {
      type: format === 'csv' ? 'text/csv;charset=utf-8' : 'application/json',
    }),
  }
}
