import { sleep } from '../lib/utils'

export const STATUS_CODES = [
  'OK',
  'SOLVER_TIMEOUT',
  'SOLVER_NOT_OPTIMAL',
  'INFEASIBLE',
  'CHECK_FAILED',
  'ERROR_DATA',
  'FALLBACK_FORECAST',
]

const MOCK_RUNS = [
  {
    runId: 'run-003',
    timestamp: '2024-11-15T08:00:00Z',
    status: 'OK',
    dataset: 'demo-supply-chain-v1',
    isSimulated: true,
    seed: 42,
    planLinesCount: 12,
    durationMs: 4200,
    solverStatusMessage: 'Optimal multi-echelon dispatch schedule converged within 0.1% optimality gap.',
    manifest: {
      datasetHash: 'sha256:7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069',
      parameters: { horizonWeeks: 12, convergenceTol: 0.001, timeoutSeconds: 60 },
      libraryVersions: {
        engine: 'Optiqo MIP Solver v2.4.1-rc3',
        highs: 'HiGHS Mixed-Integer Optimizer v1.7.0',
        pandas: '2.2.1',
      },
      exportFormats: ['csv', 'json'],
    },
  },
  {
    runId: 'run-002',
    timestamp: '2024-11-13T14:30:00Z',
    status: 'FALLBACK_FORECAST',
    dataset: 'demo-supply-chain-v1',
    isSimulated: true,
    seed: 101,
    planLinesCount: 10,
    durationMs: 3800,
    solverStatusMessage: 'Fallback moving-average forecast utilized for 2 volatile SKUs.',
    manifest: {
      datasetHash: 'sha256:7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069',
      parameters: { horizonWeeks: 12, convergenceTol: 0.001, timeoutSeconds: 60 },
      libraryVersions: {
        engine: 'Optiqo MIP Solver v2.4.1-rc3',
        highs: 'HiGHS Mixed-Integer Optimizer v1.7.0',
      },
      exportFormats: ['csv', 'json'],
    },
  },
  {
    runId: 'run-001',
    timestamp: '2024-11-11T09:15:00Z',
    status: 'OK',
    dataset: 'demo-supply-chain-v1',
    isSimulated: true,
    seed: 99,
    planLinesCount: 14,
    durationMs: 5100,
    solverStatusMessage: 'Initial network baseline solve completed successfully.',
    manifest: {
      datasetHash: 'sha256:7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069',
      parameters: { horizonWeeks: 12, convergenceTol: 0.001, timeoutSeconds: 60 },
      libraryVersions: {
        engine: 'Optiqo MIP Solver v2.4.1-rc3',
        highs: 'HiGHS Mixed-Integer Optimizer v1.7.0',
      },
      exportFormats: ['csv', 'json'],
    },
  },
  {
    runId: 'run-000-timeout',
    timestamp: '2024-11-09T18:00:00Z',
    status: 'SOLVER_TIMEOUT',
    dataset: 'demo-supply-chain-v1',
    isSimulated: true,
    seed: 88,
    planLinesCount: 8,
    durationMs: 60000,
    solverStatusMessage: 'Solver hit 60s execution timeout budget. Non-optimal incumbent returned.',
    manifest: {
      datasetHash: 'sha256:7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069',
      parameters: { horizonWeeks: 12, convergenceTol: 0.001, timeoutSeconds: 60 },
      libraryVersions: {
        engine: 'Optiqo MIP Solver v2.4.1-rc3',
        highs: 'HiGHS Mixed-Integer Optimizer v1.7.0',
      },
      exportFormats: ['csv', 'json'],
    },
  },
  {
    runId: 'run-chk-failed',
    timestamp: '2024-11-07T11:20:00Z',
    status: 'CHECK_FAILED',
    dataset: 'demo-supply-chain-v1',
    isSimulated: true,
    seed: 77,
    planLinesCount: 0,
    durationMs: 4100,
    solverStatusMessage: 'Independent constraint verifier caught negative inventory invariant violation.',
    manifest: {
      datasetHash: 'sha256:7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069',
      parameters: { horizonWeeks: 12, convergenceTol: 0.001, timeoutSeconds: 60 },
      libraryVersions: {
        engine: 'Optiqo MIP Solver v2.4.1-rc3',
        highs: 'HiGHS Mixed-Integer Optimizer v1.7.0',
      },
      exportFormats: ['json'],
    },
  },
]

/**
 * Fetch list of runs
 */
export async function getRuns({ page = 1, pageSize = 10, status } = {}) {
  await sleep(350)
  const filtered = status && status !== 'ALL' ? MOCK_RUNS.filter((r) => r.status === status) : MOCK_RUNS
  return {
    source: 'mock',
    items: filtered.slice((page - 1) * pageSize, page * pageSize),
    total: filtered.length,
    page,
    pageSize,
  }
}

/**
 * Fetch single run detail
 */
export async function getRun({ runId } = {}) {
  await sleep(250)
  const run = MOCK_RUNS.find((r) => r.runId === runId) ?? MOCK_RUNS[0]
  return { source: 'mock', ...run }
}

/**
 * Export plan or manifest
 */
export async function exportRun({ runId, format = 'csv' } = {}) {
  await sleep(400)
  return {
    source: 'mock',
    runId,
    format,
    downloadUrl: `#export-${runId}.${format}`,
    filename: `optiqo_${runId}_export.${format}`,
  }
}
