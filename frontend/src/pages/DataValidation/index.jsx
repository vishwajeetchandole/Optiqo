import { useState, useMemo } from 'react'
import {
  RefreshCw,
  Search,
  CheckCircle2,
  AlertTriangle,
  FileSpreadsheet,
  Info,
  Database,
  ArrowRight,
  ShieldCheck,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { useValidationStatus } from '@/hooks/useValidationStatus'
import { StatusBanner } from '@/components/shared/StatusBanner'
import { StatCard } from '@/components/shared/StatCard'
import { DataTable } from '@/components/shared/DataTable'
import { SeverityChip } from '@/components/shared/SeverityChip'
import { Drawer } from '@/components/shared/Drawer'
import { ProgressBar } from '@/components/shared/ProgressBar'
import { EmptyState } from '@/components/shared/EmptyState'
import { SectionCard } from '@/components/shared/SectionCard'
import { cn } from '@/lib/utils'

export default function DataValidation() {
  const {
    status,
    data,
    loading,
    error,
    progress,
    selectedDataset,
    setSelectedDataset,
    selectedFinding,
    setSelectedFinding,
    runValidation,
    refetch,
  } = useValidationStatus()

  // Filter & Search states
  const [searchQuery, setSearchQuery] = useState('')
  const [severityFilter, setSeverityFilter] = useState('ALL')
  const [tableFilter, setTableFilter] = useState('ALL')
  const [page, setPage] = useState(1)
  const pageSize = 8

  // Unique tables from checks
  const availableTables = useMemo(() => {
    if (!data?.checks) return []
    const set = new Set(data.checks.map((c) => c.table).filter(Boolean))
    return Array.from(set)
  }, [data])

  // Filtered checks list
  const filteredChecks = useMemo(() => {
    if (!data?.checks) return []
    return data.checks.filter((item) => {
      // Severity filter
      if (severityFilter !== 'ALL') {
        if (severityFilter === 'PASS' && item.status !== 'PASS') return false
        if (severityFilter === 'FAIL' && item.status !== 'FAIL') return false
        if (['warning', 'high', 'critical', 'info'].includes(severityFilter) && item.severity !== severityFilter) {
          return false
        }
      }

      // Table filter
      if (tableFilter !== 'ALL' && item.table !== tableFilter) {
        return false
      }

      // Search query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase()
        const matchName = item.name?.toLowerCase().includes(q)
        const matchMsg = item.message?.toLowerCase().includes(q)
        const matchRule = item.rule?.toLowerCase().includes(q)
        const matchField = item.field?.toLowerCase().includes(q)
        const matchTable = item.table?.toLowerCase().includes(q)
        if (!matchName && !matchMsg && !matchRule && !matchField && !matchTable) {
          return false
        }
      }

      return true
    })
  }, [data, severityFilter, tableFilter, searchQuery])

  // Paginated data for DataTable
  const paginatedChecks = useMemo(() => {
    const start = (page - 1) * pageSize
    return filteredChecks.slice(start, start + pageSize)
  }, [filteredChecks, page, pageSize])

  // Table columns definition
  const columns = [
    {
      key: 'severity',
      header: 'Severity',
      width: '110px',
      sortable: true,
      render: (val, row) => (
        <div className="flex items-center gap-1.5">
          {row.status === 'PASS' ? (
            <span className="chip chip-success flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3" />
              Pass
            </span>
          ) : (
            <SeverityChip severity={row.severity} />
          )}
        </div>
      ),
    },
    {
      key: 'table',
      header: 'Table',
      width: '140px',
      sortable: true,
      render: (val) => (
        <span className="font-mono text-xs px-2 py-0.5 rounded-md bg-[var(--color-tint)] text-ink">
          {val || '—'}
        </span>
      ),
    },
    {
      key: 'row',
      header: 'Row',
      width: '80px',
      align: 'center',
      sortable: true,
      render: (val) => (val != null ? <span className="font-mono text-xs text-muted">#{val}</span> : '—'),
    },
    {
      key: 'field',
      header: 'Field',
      width: '130px',
      render: (val) => (val ? <span className="font-mono text-xs text-ink">{val}</span> : '—'),
    },
    {
      key: 'rule',
      header: 'Rule',
      width: '160px',
      sortable: true,
      render: (val) => (
        <span className="text-xs font-semibold text-muted tracking-wide">{val || '—'}</span>
      ),
    },
    {
      key: 'message',
      header: 'Finding Message',
      render: (val, row) => (
        <div className="flex flex-col">
          <span className="font-medium text-ink">{row.name}</span>
          <span className="text-xs text-muted line-clamp-1">{val}</span>
        </div>
      ),
    },
  ]

  // Flow State Banner render
  const renderFlowBanner = () => {
    if (status === 'validating') {
      return (
        <div className="card border-[var(--color-primary-lilac)]/30 bg-[var(--color-tint)]/40 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <RefreshCw className="w-4 h-4 text-primary animate-spin" />
              <span className="font-semibold text-sm text-ink">
                Validating dataset & checking integrity rules...
              </span>
            </div>
            <span className="text-xs text-muted font-mono">{progress}%</span>
          </div>
          <ProgressBar value={progress} />
        </div>
      )
    }

    if (status === 'invalid') {
      return (
        <StatusBanner
          variant="error"
          title="Data validation failed — planning blocked"
          message={`Found ${data?.errorsCount || 0} critical error(s) preventing reliable optimization. Fix data integrity issues before running the pipeline.`}
          action={
            <button
              onClick={runValidation}
              className="pill-btn-outline text-xs px-3 py-1 flex items-center gap-1.5"
            >
              <RefreshCw className="w-3.5 h-3.5" /> Re-check
            </button>
          }
        />
      )
    }

    if (status === 'warnings-only') {
      return (
        <StatusBanner
          variant="warning"
          title="Validation passed with warnings — planning can proceed"
          message={`Found ${data?.warningsCount || 0} advisory warning(s). Planning pipeline is enabled, but review outliers to ensure forecast fidelity.`}
          action={
            <Link
              to="/plan"
              className="pill-btn-primary text-xs px-3 py-1 flex items-center gap-1.5 shadow-sm"
            >
              Proceed to Plan <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          }
        />
      )
    }

    if (status === 'valid') {
      return (
        <StatusBanner
          variant="ok"
          title="Dataset is fully valid — zero errors"
          message="All tables, reference keys, and value distributions passed schema and sanity rules."
          action={
            <Link
              to="/plan"
              className="pill-btn-primary text-xs px-3 py-1 flex items-center gap-1.5 shadow-sm"
            >
              Proceed to Plan <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          }
        />
      )
    }

    return null
  }

  return (
    <div className="flex flex-col gap-6 max-w-7xl mx-auto pb-12">
      {/* ── Top Header Controls ───────────────────────────────────────── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pt-2">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-ink flex items-center gap-2.5">
            <Database className="w-6 h-6 text-primary" />
            Data Validation
          </h1>
          <p className="text-sm text-muted mt-0.5">
            Dataset sanity checks, integrity rules, and pipeline pre-flight requirements.
          </p>
        </div>

        <div className="flex items-center flex-wrap gap-2.5">
          {/* Dataset Selector */}
          <div className="relative">
            <select
              value={selectedDataset}
              onChange={(e) => setSelectedDataset(e.target.value)}
              disabled={status === 'validating'}
              className="pill-input text-xs font-medium py-1.5 px-3 pr-8 cursor-pointer bg-[var(--color-surface)] border border-token text-ink rounded-full"
              aria-label="Select Dataset"
            >
              <option value="demo-supply-chain-v1">Demo: Global Supply Chain v1 (Active)</option>
            </select>
          </div>

          {/* Primary Validate Button */}
          <button
            onClick={runValidation}
            disabled={status === 'validating'}
            className="pill-btn-primary text-xs px-4 py-2 flex items-center gap-2 shadow-sm font-semibold"
          >
            <RefreshCw className={cn('w-3.5 h-3.5', status === 'validating' && 'animate-spin')} />
            {status === 'validating' ? 'Validating...' : 'Validate Dataset'}
          </button>
        </div>
      </div>

      {/* ── Flow State Banner ─────────────────────────────────────────── */}
      {renderFlowBanner()}

      {/* ── Summary Stat Cards (4) ────────────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Tables Checked"
          value={data?.tablesChecked ?? 0}
          loading={loading}
          unit="tables"
        />
        <StatCard
          label="Critical Errors"
          value={data?.errorsCount ?? 0}
          loading={loading}
          unit="blocking"
          deltaPositiveIsGood={false}
          className={data?.errorsCount > 0 ? 'border-red-400 dark:border-red-800' : ''}
        />
        <StatCard
          label="Advisory Warnings"
          value={data?.warningsCount ?? 0}
          loading={loading}
          unit="findings"
          deltaPositiveIsGood={false}
        />
        <StatCard
          label="Rows Scanned"
          value={data?.rowsScanned ?? 0}
          loading={loading}
          unit="rows"
        />
      </div>

      {/* ── Findings Section & Table ──────────────────────────────────── */}
      <SectionCard
        title="Validation Findings & Schema Checks"
        subtitle={`Showing ${filteredChecks.length} checks (${filteredChecks.filter((c) => c.status === 'PASS').length} pass, ${filteredChecks.filter((c) => c.status === 'FAIL').length} flagged)`}
        controls={
          <div className="flex items-center gap-2 flex-wrap">
            {/* Search */}
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-muted absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                type="text"
                placeholder="Search rule, field, message..."
                aria-label="Search rule, field, or message"
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value)
                  setPage(1)
                }}
                className="pill-input text-xs pl-8 pr-3 py-1 bg-[var(--color-surface)] border border-token text-ink rounded-full w-48 lg:w-60 focus:w-72 transition-all"
              />
            </div>

            {/* Severity Filter */}
            <select
              value={severityFilter}
              aria-label="Filter checks by severity"
              onChange={(e) => {
                setSeverityFilter(e.target.value)
                setPage(1)
              }}
              className="pill-input text-xs py-1 px-2.5 bg-[var(--color-surface)] border border-token text-ink rounded-full cursor-pointer"
            >
              <option value="ALL">All Severities</option>
              <option value="FAIL">Flagged (Fail/Warn)</option>
              <option value="PASS">Passed Checks</option>
              <option value="warning">Warnings</option>
              <option value="high">High/Critical</option>
            </select>

            {/* Table Filter */}
            {availableTables.length > 0 && (
              <select
                value={tableFilter}
                aria-label="Filter checks by table"
                onChange={(e) => {
                  setTableFilter(e.target.value)
                  setPage(1)
                }}
                className="pill-input text-xs py-1 px-2.5 bg-[var(--color-surface)] border border-token text-ink rounded-full cursor-pointer"
              >
                <option value="ALL">All Tables</option>
                {availableTables.map((tbl) => (
                  <option key={tbl} value={tbl}>
                    {tbl}
                  </option>
                ))}
              </select>
            )}
          </div>
        }
      >
        <DataTable
          columns={columns}
          data={paginatedChecks}
          loading={loading || status === 'validating'}
          error={error}
          onRetry={refetch}
          onRowClick={(row) => setSelectedFinding(row)}
          rowKey="id"
          total={filteredChecks.length}
          page={page}
          pageSize={pageSize}
          onPageChange={(p) => setPage(p)}
          emptyTitle="No validation findings match your filter"
          emptyMessage="Try adjusting the search query or severity selector above."
        />
      </SectionCard>

      {/* ── Usable vs Unusable Inventory Summary (PRD P0-03) ──────────── */}
      <div className="card p-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h3 className="text-base font-bold text-ink flex items-center gap-2">
              <FileSpreadsheet className="w-4 h-4 text-primary" />
              Usable vs. Unusable Inventory Breakdown (PRD P0-03)
            </h3>
            <p className="text-xs text-muted mt-0.5">
              Partitioning inventory into active, expired, damaged, or quarantined stock.
            </p>
          </div>
          <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-[var(--color-tint)] text-primary">
            Contract: inventorySummary
          </span>
        </div>

        <EmptyState
          icon={Info}
          title="Not available in current dataset"
          message="Usable vs. unusable inventory categorization requires warehouse lot-level expiry and quarantine tags, which are not exposed in demo dataset v1. Once batch tracking metadata is attached by backend, an active breakdown chart will render here."
          className="py-8"
        />
      </div>

      {/* ── Finding Detail Drawer ────────────────────────────────────── */}
      <Drawer
        open={Boolean(selectedFinding)}
        onClose={() => setSelectedFinding(null)}
        title={selectedFinding?.name || 'Finding Detail'}
        subtitle={`Check ID: ${selectedFinding?.id || '—'} · Run ${data?.runId || 'val-003'}`}
      >
        {selectedFinding && (
          <div className="space-y-6">
            {/* Status & Severity */}
            <div className="p-4 rounded-xl bg-[var(--color-tint)]/60 border border-token flex items-center justify-between">
              <div className="flex items-center gap-2">
                {selectedFinding.status === 'PASS' ? (
                  <span className="chip chip-success flex items-center gap-1 font-semibold text-xs">
                    <CheckCircle2 className="w-3.5 h-3.5" /> PASSED
                  </span>
                ) : (
                  <span className="chip chip-warning flex items-center gap-1 font-semibold text-xs">
                    <AlertTriangle className="w-3.5 h-3.5" /> FLAGGED
                  </span>
                )}
                <SeverityChip severity={selectedFinding.severity} />
              </div>
              <span className="text-xs font-mono text-muted">Rule: {selectedFinding.rule}</span>
            </div>

            {/* Description / Message */}
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider text-muted mb-1.5">
                Finding Message
              </h4>
              <p className="text-sm text-ink leading-relaxed p-3.5 rounded-xl border border-token bg-[var(--color-surface)]">
                {selectedFinding.message}
              </p>
            </div>

            {/* Target Location Metadata */}
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider text-muted mb-2">
                Schema Coordinates
              </h4>
              <div className="grid grid-cols-3 gap-3">
                <div className="p-3 rounded-xl border border-token bg-[var(--color-surface)]">
                  <span className="text-[11px] text-muted block">Table</span>
                  <span className="font-mono text-xs font-bold text-ink">
                    {selectedFinding.table || '—'}
                  </span>
                </div>
                <div className="p-3 rounded-xl border border-token bg-[var(--color-surface)]">
                  <span className="text-[11px] text-muted block">Row #</span>
                  <span className="font-mono text-xs font-bold text-ink">
                    {selectedFinding.row != null ? `#${selectedFinding.row}` : 'Global check'}
                  </span>
                </div>
                <div className="p-3 rounded-xl border border-token bg-[var(--color-surface)]">
                  <span className="text-[11px] text-muted block">Field</span>
                  <span className="font-mono text-xs font-bold text-ink">
                    {selectedFinding.field || '—'}
                  </span>
                </div>
              </div>
            </div>

            {/* Resolution Guidance */}
            <div className="p-4 rounded-xl border border-token bg-[var(--color-surface)] space-y-2">
              <h4 className="text-xs font-bold uppercase tracking-wider text-primary flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4" /> Recommended Action
              </h4>
              <p className="text-xs text-muted leading-relaxed">
                {selectedFinding.status === 'PASS'
                  ? 'No action needed. This check meets all validation invariants.'
                  : selectedFinding.rule === 'OUTLIER_Z_SCORE'
                  ? 'Inspect source ERP/POS transactions for SKU-1042 during week W11. If this represents a promotional one-time spike, consider winsorizing or tagging as an event override.'
                  : selectedFinding.rule === 'ZERO_DEMAND_STREAK'
                  ? 'Confirm whether SKU-2198 was discontinued, phased out, or suffered an upstream supply shortage causing zero demand records.'
                  : selectedFinding.rule === 'FRESHNESS_CHECK'
                  ? 'Trigger an ad-hoc sync job with warehouse WH-3 inventory management system to refresh the snapshot.'
                  : 'Review the flagged rows and re-validate once corrected.'}
              </p>
            </div>

            {/* Technical Payload Inspector */}
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider text-muted mb-2">
                Raw Rule Diagnostic Payload
              </h4>
              <pre className="text-[11px] font-mono p-3.5 rounded-xl bg-[var(--color-tint)] text-ink border border-token overflow-x-auto">
                {JSON.stringify(selectedFinding, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </Drawer>
    </div>
  )
}
