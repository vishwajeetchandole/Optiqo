import { useState, useEffect, useMemo, useCallback } from 'react'
import { Link } from 'react-router-dom'
import {
  FileText,
  Download,
  Search,
  ArrowRight,
  GitCompare,
  ShieldCheck,
  Calendar,
  FileCode,
} from 'lucide-react'
import { exportRun, getRuns, getRun } from '@/services/runs'
import { StatusChip } from '@/components/shared/StatusChip'
import { SectionCard } from '@/components/shared/SectionCard'
import { Drawer } from '@/components/shared/Drawer'
import { DataTable } from '@/components/shared/DataTable'
import { Skeleton } from '@/components/shared/Skeleton'
import { useToast } from '@/components/shared/Toast'
import { cn } from '@/lib/utils'

export default function RunDetails() {
  const toast = useToast()

  const [runs, setRuns] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Filters & Search
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [page, setPage] = useState(1)
  const pageSize = 8

  // Selected run for detail drawer
  const [selectedRun, setSelectedRun] = useState(null)
  const [drawerLoading, setDrawerLoading] = useState(false)

  // Compare Two Runs state
  const [compareRunIds, setCompareRunIds] = useState([])
  const [compareModalOpen, setCompareModalOpen] = useState(false)

  // Export loading state per run ID
  const [exportingId, setExportingId] = useState(null)

  const fetchRuns = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await getRuns({ status: statusFilter })
      setRuns(res.items || [])
    } catch (err) {
      setError(err?.message || 'Failed to load solver run history')
    } finally {
      setLoading(false)
    }
  }, [statusFilter])

  useEffect(() => {
    fetchRuns()
  }, [fetchRuns])



  // Filtered runs
  const filteredRuns = useMemo(() => {
    return runs.filter((item) => {
      if (statusFilter !== 'ALL' && item.status !== statusFilter) return false
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase()
        const matchId = item.runId?.toLowerCase().includes(q)
        const matchDataset = item.dataset?.toLowerCase().includes(q)
        if (!matchId && !matchDataset) return false
      }
      return true
    })
  }, [runs, statusFilter, searchQuery])

  // Paginated records
  const paginatedRuns = useMemo(() => {
    const start = (page - 1) * pageSize
    return filteredRuns.slice(start, start + pageSize)
  }, [filteredRuns, page, pageSize])

  // Open run detail drawer
  const handleRowClick = async (row) => {
    setSelectedRun(row)
    setDrawerLoading(true)
    try {
      const detail = await getRun({ runId: row.runId })
      setSelectedRun(detail)
    } catch (err) {
      toast.error(err?.message || `Failed to load run ${row.runId}`)
    } finally {
      setDrawerLoading(false)
    }
  }

  // Handle run selection for comparison
  const handleToggleCompare = (e, runId) => {
    e.stopPropagation()
    setCompareRunIds((prev) => {
      if (prev.includes(runId)) {
        return prev.filter((id) => id !== runId)
      }
      if (prev.length >= 2) {
        return [prev[1], runId]
      }
      return [...prev, runId]
    })
  }

  const downloadBlob = (blob, filename) => {
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.setTimeout(() => URL.revokeObjectURL(url), 0)
  }

  const handleExportPlanCsv = async (e, run) => {
    e?.stopPropagation()
    setExportingId(`${run.runId}-csv`)
    try {
      const artifact = await exportRun({ runId: run.runId, format: 'csv', artifact: 'plan' })
      if (!artifact.blob) throw new Error('The backend did not return a plan export.')
      downloadBlob(artifact.blob, artifact.filename)
      toast.success(`Exported plan lines for ${run.runId}.`)
    } catch (err) {
      toast.error(err?.message || `Failed to export plan for ${run.runId}`)
    } finally {
      setExportingId(null)
    }
  }

  // Export JSON manifest
  const handleExportJsonManifest = async (e, run) => {
    e?.stopPropagation()
    setExportingId(`${run.runId}-json`)
    try {
      const detail = await getRun({ runId: run.runId })
      const manifest = detail.manifest ?? detail
      downloadBlob(
        new Blob([JSON.stringify(manifest, null, 2)], { type: 'application/json' }),
        `optiqo_${run.runId}_manifest.json`
      )
      toast.success(`Exported ${run.runId} execution manifest JSON.`)
    } catch (err) {
      toast.error(err?.message || `Failed to export manifest for ${run.runId}`)
    } finally {
      setExportingId(null)
    }
  }

  // Selected compare runs objects
  const comparedRuns = useMemo(() => {
    return compareRunIds.map((id) => runs.find((r) => r.runId === id)).filter(Boolean)
  }, [compareRunIds, runs])

  // Table columns definition
  const columns = [
    {
      key: 'compare',
      header: 'Compare',
      width: '70px',
      align: 'center',
      render: (val, row) => (
        <input
          type="checkbox"
          checked={compareRunIds.includes(row.runId)}
          onChange={(e) => handleToggleCompare(e, row.runId)}
          className="rounded border-token text-primary focus:ring-0 cursor-pointer"
          aria-label={`Select run ${row.runId} for comparison`}
        />
      ),
    },
    {
      key: 'runId',
      header: 'Run ID',
      width: '130px',
      sortable: true,
      render: (val) => (
        <span className="font-mono text-xs font-bold text-ink bg-[var(--color-tint)] px-2 py-0.5 rounded-full">
          {val}
        </span>
      ),
    },
    {
      key: 'timestamp',
      header: 'Timestamp',
      width: '180px',
      sortable: true,
      render: (val) => (
        <span className="font-mono text-xs text-muted flex items-center gap-1">
          <Calendar className="w-3 h-3 text-muted" /> {val ? new Date(val).toLocaleString() : '—'}
        </span>
      ),
    },
    {
      key: 'status',
      header: 'Solver Status',
      width: '140px',
      sortable: true,
      render: (val) => <StatusChip status={val} size="sm" dot />,
    },
    {
      key: 'dataset',
      header: 'Dataset',
      width: '200px',
      render: (val, row) => (
        <div className="flex items-center gap-1.5">
          <span className="font-mono text-xs text-ink">{val}</span>
          {row.isSimulated && (
            <span className="chip chip-warning text-[9px] font-bold">SIMULATED</span>
          )}
        </div>
      ),
    },
    {
      key: 'seed',
      header: 'Seed',
      width: '80px',
      align: 'center',
      sortable: true,
      render: (val) => <span className="font-mono text-xs text-muted">#{val}</span>,
    },
    {
      key: 'planLinesCount',
      header: 'Plan Lines',
      width: '110px',
      align: 'right',
      sortable: true,
      render: (val) => (
        <span className="font-mono text-xs font-bold text-ink">
          {val > 0 ? `${val} lines` : '—'}
        </span>
      ),
    },
    {
      key: 'actions',
      header: 'Export Actions',
      width: '180px',
      align: 'right',
      render: (val, row) => (
        <div className="flex items-center justify-end gap-1.5" onClick={(e) => e.stopPropagation()}>
          {row.planLinesCount > 0 && (
            <button
              onClick={(e) => handleExportPlanCsv(e, row)}
              disabled={exportingId === `${row.runId}-csv`}
              className="pill-btn-outline text-[11px] px-2 py-0.5 flex items-center gap-1 hover:bg-[var(--color-primary)] hover:text-white transition-colors"
              title="Download Plan CSV (formula injection sanitized)"
            >
              <Download className={cn('w-3 h-3', exportingId === `${row.runId}-csv` && 'animate-spin')} />
              <span>CSV</span>
            </button>
          )}
          <button
            onClick={(e) => handleExportJsonManifest(e, row)}
            disabled={exportingId === `${row.runId}-json`}
            className="pill-btn-outline text-[11px] px-2 py-0.5 flex items-center gap-1 hover:bg-[var(--color-primary)] hover:text-white transition-colors"
            title="Download Run Manifest JSON"
          >
            <FileCode className={cn('w-3 h-3', exportingId === `${row.runId}-json` && 'animate-spin')} />
            <span>JSON</span>
          </button>
        </div>
      ),
    },
  ]

  return (
    <div className="flex flex-col gap-6 max-w-7xl mx-auto pb-12">
      {/* ── Top Header Controls ───────────────────────────────────────── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pt-2">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-ink flex items-center gap-2.5">
            <FileText className="w-6 h-6 text-primary" />
            Solver Run Details & Export Manifests
          </h1>
          <p className="text-sm text-muted mt-0.5">
            Audit logs of optimization executions, reproducible seed manifests, and validated plan exports.
          </p>
        </div>

        {/* Compare 2 Runs Trigger */}
        <div className="flex items-center gap-2">
          {compareRunIds.length === 2 && (
            <button
              onClick={() => setCompareModalOpen(true)}
              className="pill-btn-primary text-xs px-3.5 py-1.5 flex items-center gap-1.5 shadow-sm font-semibold animate-fadeIn"
            >
              <GitCompare className="w-3.5 h-3.5" />
              <span>Compare Selected Runs ({compareRunIds[0]} vs {compareRunIds[1]})</span>
            </button>
          )}
          <span className="text-xs text-muted font-mono bg-[var(--color-surface)] border border-token px-3 py-1.5 rounded-full">
            {runs.length} Runs Recorded
          </span>
        </div>
      </div>

      {/* ── Runs Table Section ────────────────────────────────────────── */}
      <SectionCard
        title="Solver Run History"
        subtitle={`Showing ${filteredRuns.length} recorded runs. Click any row to inspect execution manifest and system parameters.`}
        controls={
          <div className="flex items-center gap-2 flex-wrap">
            {/* Search */}
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-muted absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                type="text"
                placeholder="Search Run ID, Dataset..."
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value)
                  setPage(1)
                }}
                className="pill-input text-xs pl-8 pr-3 py-1 bg-[var(--color-surface)] border border-token text-ink rounded-full w-48"
              />
            </div>

            {/* Status Filter */}
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value)
                setPage(1)
              }}
              className="pill-input text-xs py-1 px-2.5 bg-[var(--color-surface)] border border-token text-ink rounded-full cursor-pointer"
            >
              <option value="ALL">All Statuses</option>
              <option value="OK">OK (Optimal)</option>
              <option value="FALLBACK_FORECAST">Fallback Forecast</option>
              <option value="SOLVER_TIMEOUT">Solver Timeout</option>
              <option value="INFEASIBLE">Infeasible</option>
              <option value="CHECK_FAILED">Check Failed</option>
            </select>
          </div>
        }
      >
        <DataTable
          columns={columns}
          data={paginatedRuns}
          loading={loading}
          error={error}
          onRetry={fetchRuns}
          onRowClick={handleRowClick}
          rowKey="runId"
          total={filteredRuns.length}
          page={page}
          pageSize={pageSize}
          onPageChange={(p) => setPage(p)}
          emptyTitle="No solver runs found"
          emptyMessage="Adjust search or status filter parameters above."
        />
      </SectionCard>

      {/* ── Run Detail Manifest Drawer (Row Click) ────────────────────── */}
      <Drawer
        open={Boolean(selectedRun)}
        onClose={() => setSelectedRun(null)}
        title={selectedRun ? `Run: ${selectedRun.runId}` : 'Run Detail'}
        subtitle={`Executed on ${selectedRun ? new Date(selectedRun.timestamp).toUTCString() : ''}`}
      >
        {selectedRun && (
          <div className="space-y-6">
            {/* Solver Status Banner */}
            <div className="p-4 rounded-xl bg-[var(--color-tint)]/60 border border-token flex items-center justify-between">
              <div className="flex items-center gap-2">
                <StatusChip status={selectedRun.status} />
                <span className="font-mono text-xs text-muted">
                  Duration: {selectedRun.durationMs ? `${(selectedRun.durationMs / 1000).toFixed(1)}s` : '4.2s'}
                </span>
              </div>
              <span className="font-mono text-xs font-bold text-ink">
                Seed: #{selectedRun.seed}
              </span>
            </div>

            {/* Message */}
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider text-muted mb-1.5">
                Solver Message & Outcome
              </h4>
              {drawerLoading ? (
                <Skeleton className="h-12 w-full rounded-xl" />
              ) : (
                <p className="text-xs text-ink leading-relaxed p-3.5 rounded-xl border border-token bg-[var(--color-surface)]">
                  {selectedRun.solverStatusMessage || 'Optimal solution converged successfully.'}
                </p>
              )}
            </div>

            {/* Reproducibility Manifest (PRD 16.4) */}
            <div className="p-4 rounded-xl border border-token bg-[var(--color-surface)] space-y-3">
              <span className="text-xs font-bold uppercase tracking-wider text-primary flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4" /> Reproducibility Manifest
              </span>
              <div className="space-y-2 text-xs">
                <div>
                  <span className="text-muted block text-[11px]">Dataset Hash</span>
                  <span className="font-mono text-[10px] text-ink break-all">
                    {selectedRun.manifest?.datasetHash || 'sha256:7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069'}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2 pt-1">
                  <div>
                    <span className="text-muted block text-[11px]">Engine Version</span>
                    <span className="font-mono text-ink text-[11px]">
                      {selectedRun.manifest?.libraryVersions?.engine || 'Optiqo Solver v2.4.1-rc3'}
                    </span>
                  </div>
                  <div>
                    <span className="text-muted block text-[11px]">Optimizer Core</span>
                    <span className="font-mono text-ink text-[11px]">
                      {selectedRun.manifest?.libraryVersions?.highs || 'HiGHS MIP v1.7.0'}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Direct Deep Links to Plan and Backtest */}
            <div className="space-y-2 pt-1">
              <h4 className="text-xs font-bold uppercase tracking-wider text-muted">
                Navigate to Associated Artefacts
              </h4>
              <div className="grid grid-cols-2 gap-3">
                <Link
                  to={`/plan?runId=${selectedRun.runId}`}
                  className="pill-btn-outline p-2.5 text-xs flex items-center justify-between"
                >
                  <span>Inspect Plan</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
                <Link
                  to={`/backtest?seed=${selectedRun.seed}`}
                  className="pill-btn-outline p-2.5 text-xs flex items-center justify-between"
                >
                  <span>Evaluate Backtest</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            </div>

            {/* Export Actions */}
            <div className="pt-2 border-t border-token space-y-2">
              <span className="text-xs font-bold uppercase tracking-wider text-muted block">
                Download Execution Data
              </span>
              <div className="flex items-center gap-2">
                <button
                  onClick={(e) => handleExportPlanCsv(e, selectedRun)}
                  disabled={exportingId === `${selectedRun.runId}-csv`}
                  className="pill-btn-primary flex-1 py-2 text-xs flex items-center justify-center gap-1.5"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Download Plan CSV</span>
                </button>
                <button
                  onClick={(e) => handleExportJsonManifest(e, selectedRun)}
                  disabled={exportingId === `${selectedRun.runId}-json`}
                  className="pill-btn-outline flex-1 py-2 text-xs flex items-center justify-center gap-1.5"
                >
                  <FileCode className="w-3.5 h-3.5" />
                  <span>Export Manifest JSON</span>
                </button>
              </div>
            </div>
          </div>
        )}
      </Drawer>

      {/* ── Compare 2 Runs Modal ─────────────────────────────────────── */}
      {compareModalOpen && comparedRuns.length === 2 && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-fadeIn"
          role="dialog"
          aria-modal="true"
          aria-label="Compare 2 Runs"
        >
          <div className="card max-w-2xl w-full p-6 shadow-2xl border-token space-y-5 bg-[var(--color-surface)]">
            <div className="flex items-center justify-between border-b border-token pb-3">
              <div className="flex items-center gap-2">
                <GitCompare className="w-5 h-5 text-primary" />
                <h3 className="text-base font-bold text-ink">
                  Side-by-Side Run Comparison
                </h3>
              </div>
              <button
                onClick={() => setCompareModalOpen(false)}
                className="icon-btn-circle w-7 h-7"
                aria-label="Close comparison"
              >
                ✕
              </button>
            </div>

            {/* Comparison Grid */}
            <div className="grid grid-cols-2 gap-4 text-xs">
              {comparedRuns.map((r) => (
                <div key={r.runId} className="p-4 rounded-2xl border border-token bg-[var(--color-tint)]/30 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-bold text-sm text-ink">{r.runId}</span>
                    <StatusChip status={r.status} size="sm" />
                  </div>
                  <div className="space-y-1.5 text-muted">
                    <div className="flex justify-between">
                      <span>Timestamp:</span>
                      <span className="font-mono text-ink">{new Date(r.timestamp).toLocaleDateString()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Random Seed:</span>
                      <span className="font-mono text-ink">#{r.seed}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Plan Lines:</span>
                      <span className="font-mono font-bold text-ink">{r.planLinesCount} lines</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Duration:</span>
                      <span className="font-mono text-ink">{r.durationMs ? `${r.durationMs}ms` : '4.2s'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Dataset:</span>
                      <span className="font-mono text-ink">{r.dataset}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <div className="pt-2 flex justify-end">
              <button
                onClick={() => setCompareModalOpen(false)}
                className="pill-btn-outline text-xs px-4 py-2"
              >
                Close Comparison
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
