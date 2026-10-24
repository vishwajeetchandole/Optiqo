import { useState, useEffect, useMemo, useCallback } from 'react'
import {
  RotateCcw,
  Search,
  ArrowRight,
  AlertCircle,
} from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts'
import { getRiskOverview } from '@/services/risk'
import { StatCard } from '@/components/shared/StatCard'
import { SectionCard } from '@/components/shared/SectionCard'
import { ChartCard, ChartTooltip } from '@/components/shared/ChartCard'
import { SeverityChip } from '@/components/shared/SeverityChip'
import { Drawer } from '@/components/shared/Drawer'
import { DataTable } from '@/components/shared/DataTable'
import { PageLayout } from '@/components/shared/PageLayout'
import { ErrorState } from '@/components/shared/ErrorState'
import { CardSkeleton } from '@/components/shared/Skeleton'
import { cn, CHART_COLORS } from '@/lib/utils'

export default function RiskOverview() {
  const [searchParams, setSearchParams] = useSearchParams()
  const initialRegion = searchParams.get('region') || 'ALL'
  const initialSeverity = searchParams.get('severity') || 'ALL'
  const initialType = searchParams.get('type') || 'ALL'
  const initialQ = searchParams.get('q') || searchParams.get('sku') || ''

  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Drawer state for selected pair
  const [selectedPair, setSelectedPair] = useState(null)

  // Filter states initialized from URL query params
  const [searchQuery, setSearchQuery] = useState(initialQ)
  const [selectedRegion, setSelectedRegion] = useState(initialRegion)
  const [selectedSeverity, setSelectedSeverity] = useState(initialSeverity)
  const [selectedRiskType, setSelectedRiskType] = useState(initialType)

  // Sync state to URL query params
  useEffect(() => {
    const params = new URLSearchParams()
    if (selectedRegion !== 'ALL') params.set('region', selectedRegion)
    if (selectedSeverity !== 'ALL') params.set('severity', selectedSeverity)
    if (selectedRiskType !== 'ALL') params.set('type', selectedRiskType)
    if (searchQuery.trim()) params.set('q', searchQuery.trim())
    setSearchParams(params, { replace: true })
  }, [selectedRegion, selectedSeverity, selectedRiskType, searchQuery, setSearchParams])

  // Sorting state: when null, preserves backend default ranking!
  const [activeSort, setActiveSort] = useState(null) // { key: string, dir: 'asc' | 'desc' } | null
  const [page, setPage] = useState(1)
  const pageSize = 8

  // Load data
  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await getRiskOverview()
      setData(res)
    } catch (err) {
      setError(err?.message || 'Failed to load risk overview')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    let mounted = true
    async function init() {
      setLoading(true)
      setError(null)
      try {
        const res = await getRiskOverview()
        if (mounted) setData(res)
      } catch (err) {
        if (mounted) setError(err?.message || 'Failed to load risk overview')
      } finally {
        if (mounted) setLoading(false)
      }
    }
    init()
    return () => {
      mounted = false
    }
  }, [])

  // Filtered pairs
  const filteredPairs = useMemo(() => {
    if (!data?.rankedPairs) return []

    let list = data.rankedPairs.filter((item) => {
      // Region filter
      if (selectedRegion !== 'ALL' && item.region !== selectedRegion) return false

      // Severity filter
      if (selectedSeverity !== 'ALL' && item.severity !== selectedSeverity) return false

      // Risk type filter
      if (selectedRiskType !== 'ALL' && item.riskType !== selectedRiskType) return false

      // Text search
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase()
        const matchSku = item.sku?.toLowerCase().includes(q)
        const matchProduct = item.productName?.toLowerCase().includes(q)
        const matchDest = item.destination?.toLowerCase().includes(q)
        const matchRationale = item.rationale?.toLowerCase().includes(q)
        if (!matchSku && !matchProduct && !matchDest && !matchRationale) return false
      }

      return true
    })

    // If activeSort is set, sort. Otherwise, PRESERVE default backend ranking!
    if (activeSort) {
      list = [...list].sort((a, b) => {
        const av = a[activeSort.key]
        const bv = b[activeSort.key]
        if (av == null) return 1
        if (bv == null) return -1
        const cmp = typeof av === 'string' ? av.localeCompare(bv) : av - bv
        return activeSort.dir === 'asc' ? cmp : -cmp
      })
    }

    return list
  }, [data, selectedRegion, selectedSeverity, selectedRiskType, searchQuery, activeSort])

  // Paginated records
  const paginatedPairs = useMemo(() => {
    const start = (page - 1) * pageSize
    return filteredPairs.slice(start, start + pageSize)
  }, [filteredPairs, page, pageSize])

  // Handle column sort request
  const handleColumnSort = (key) => {
    if (!activeSort || activeSort.key !== key) {
      setActiveSort({ key, dir: 'asc' })
    } else if (activeSort.dir === 'asc') {
      setActiveSort({ key, dir: 'desc' })
    } else {
      setActiveSort(null) // reset to default ranking
    }
  }

  // Reset to default ranking
  const resetToDefaultRanking = () => {
    setActiveSort(null)
  }

  // Columns definition for DataTable
  const columns = [
    {
      key: 'rank',
      header: 'Rank',
      width: '70px',
      align: 'center',
      sortable: true,
      render: (val) => (
        <span className="font-mono text-xs font-bold text-muted bg-[var(--color-tint)] px-2 py-0.5 rounded-full">
          #{row.rank}
        </span>
      ),
    },
    {
      key: 'severity',
      header: 'Severity',
      width: '100px',
      sortable: true,
      render: (val) => <SeverityChip severity={val} />,
    },
    {
      key: 'riskType',
      header: 'Risk Type',
      width: '100px',
      sortable: true,
      render: (val) => {
        const colorClass =
          val === 'Stockout'
            ? 'chip-danger'
            : val === 'Expiry'
            ? 'chip-warning'
            : 'chip-neutral'
        return <span className={cn('chip text-[0.7rem] font-semibold', colorClass)}>{val}</span>
      },
    },
    {
      key: 'sku',
      header: 'SKU & Description',
      width: '200px',
      sortable: true,
      render: (val, row) => (
        <div className="flex flex-col">
          <span className="font-mono text-xs font-bold text-ink">{val}</span>
          <span className="text-[11px] text-muted line-clamp-1">{row.productName}</span>
        </div>
      ),
    },
    {
      key: 'destination',
      header: 'Destination & Region',
      width: '180px',
      sortable: true,
      render: (val, row) => (
        <div className="flex flex-col">
          <span className="text-xs font-medium text-ink">{val}</span>
          <span className="text-[10px] text-muted font-mono">{row.region}</span>
        </div>
      ),
    },
    {
      key: 'daysOfCover',
      header: 'Cover (Days)',
      width: '110px',
      align: 'right',
      sortable: true,
      render: (val) => (
        <span
          className={cn(
            'font-mono text-xs font-semibold',
            val < 7 ? 'text-danger' : val > 90 ? 'text-warning' : 'text-ink'
          )}
        >
          {val.toFixed(1)} d
        </span>
      ),
    },
    {
      key: 'expectedUnmetDemand',
      header: 'Unmet Demand',
      width: '130px',
      align: 'right',
      sortable: true,
      render: (val) =>
        val > 0 ? (
          <span className="font-mono text-xs font-bold text-danger">
            {val.toLocaleString()} units
          </span>
        ) : (
          <span className="text-xs text-muted">—</span>
        ),
    },
    {
      key: 'expectedExpiryLoss',
      header: 'Expiry Cost',
      width: '130px',
      align: 'right',
      sortable: true,
      render: (val) =>
        val > 0 ? (
          <span className="font-mono text-xs font-bold text-warning">
            {val.toLocaleString()} cost units
          </span>
        ) : (
          <span className="text-xs text-muted">—</span>
        ),
    },
    {
      key: 'drivers',
      header: 'Key Metric Driver',
      render: (val, row) => (
        <div className="flex items-center gap-2 text-xs">
          <span className="text-muted">{val.primaryDriver || 'No driver details provided'}</span>
        </div>
      ),
    },
  ]

  const summary = data?.summaryCards || {}
  const riskChartData = Object.entries(data?.riskCounts ?? {}).map(([riskType, alerts]) => ({
    riskType,
    alerts,
  }))

  const pageActions = (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-muted">Assessment Run:</span>
      <span className="font-mono font-semibold text-ink bg-[var(--color-surface)] border border-token px-2.5 py-1 rounded-full tabular-nums">
        {data?.runId || '—'}
      </span>
      <span className="text-muted font-mono text-[11px] tabular-nums">
        {data?.originDate ? `· ${data.originDate}` : ''}
      </span>
    </div>
  )

  const summaryCardsContent = loading && !data ? (
    Array.from({ length: 4 }).map((_, i) => <CardSkeleton key={i} />)
  ) : error && !data ? (
    <div className="col-span-full"><ErrorState error={new Error(error)} onRetry={fetchData} /></div>
  ) : (
    <>
      <StatCard
        label="Total Risk Alerts"
        value={summary.totalAlerts ?? 0}
        unit="alerts"
      />
      <StatCard
        label="Critical"
        value={summary.critical ?? 0}
        unit="pairs"
        deltaPositiveIsGood={false}
        className="border-red-400 dark:border-red-900 bg-red-50/20"
      />
      <StatCard
        label="High"
        value={summary.high ?? 0}
        unit="pairs"
        deltaPositiveIsGood={false}
      />
      <StatCard
        label="Medium & Low"
        value={(summary.medium ?? 0) + (summary.low ?? 0)}
        unit="pairs"
      />
    </>
  )

  return (
    <PageLayout
      actions={pageActions}
      summaryCards={summaryCardsContent}
    >

      {/* ── Network-Level Supply Shortages (PRD J2 — Listed Separately) ── */}
      <div className="card p-6 border-red-200 dark:border-red-950/60 bg-gradient-to-r from-red-50/30 via-[var(--color-surface)] to-[var(--color-surface)]">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-red-500 animate-pulse" />
              <h2 className="text-base font-bold text-ink">
                Network-Level Supply Shortages (Global Constraints)
              </h2>
              <span className="chip chip-danger text-[11px] font-bold">
                {data?.networkShortages?.length || 0} Shortage SKUs
              </span>
            </div>
            <p className="text-xs text-muted mt-0.5">
              SKUs reported by the backend as having a network-level supply shortage.
            </p>
          </div>
          <span className="text-[11px] font-mono text-muted bg-[var(--color-surface)] px-2.5 py-1 rounded-full border border-token">
            PRD Journey J2
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {(data?.networkShortages || []).map((shortage) => (
            <div
              key={shortage.shortageId}
              className="p-4 rounded-2xl border border-token bg-[var(--color-surface)] shadow-sm hover:border-[var(--color-primary-lilac)] transition-all flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="font-mono text-xs font-bold text-ink">
                    {shortage.sku}
                  </span>
                  <span className="chip chip-danger text-[10px]">Supply shortage</span>
                </div>
                <p className="text-xs text-muted mt-2 leading-relaxed">
                  The API identifies this SKU as short at network level. It does not include a
                  quantified deficit, regional breakdown, or mitigation recommendation.
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Network Risk Breakdown Chart Card ────────────────────────── */}
      <ChartCard
        title="Risk Alerts by Type"
        subtitle="Network-wide counts returned by the risk assessment API"
        chartHeight={240}
      >
        <BarChart
          data={riskChartData}
          margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
        >
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--color-border)" />
          <XAxis
            dataKey="riskType"
            stroke="var(--color-muted)"
            fontSize={11}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            stroke="var(--color-muted)"
            fontSize={11}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip content={<ChartTooltip />} />
          <Bar dataKey="alerts" fill={CHART_COLORS.danger} radius={[4, 4, 0, 0]} name="Alerts" />
        </BarChart>
      </ChartCard>

      {/* ── Ranked SKU–Destination Pairs Table ───────────────────────── */}
      <SectionCard
        title="Ranked SKU–Destination Pairs"
        subtitle={`Showing ${filteredPairs.length} ranked pairs. Evaluated by multi-factor risk scoring engine.`}
        controls={
          <div className="flex items-center gap-2 flex-wrap">
            {/* Active Sort Indicator & Reset to Default Ranking */}
            {activeSort ? (
              <div className="flex items-center gap-1.5 bg-[var(--color-tint)] px-2.5 py-1 rounded-full border border-token text-xs text-primary font-medium animate-fadeIn">
                <span>
                  Sorted by <strong className="font-bold">{activeSort.key}</strong> ({activeSort.dir})
                </span>
                <button
                  onClick={resetToDefaultRanking}
                  className="icon-btn-circle w-4 h-4 ml-1 hover:bg-white dark:hover:bg-black"
                  title="Reset to default backend ranking"
                  aria-label="Reset to default backend ranking"
                >
                  <RotateCcw className="w-2.5 h-2.5" />
                </button>
              </div>
            ) : (
              <span className="text-[11px] font-mono text-muted px-2 py-0.5 rounded-full bg-[var(--color-tint)]">
                Default Backend Ranking
              </span>
            )}

            {/* Search Query */}
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-muted absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                type="text"
                placeholder="Search SKU, Destination..."
                aria-label="Search SKU or destination"
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value)
                  setPage(1)
                }}
                className="pill-input text-xs pl-8 pr-3 py-1 bg-[var(--color-surface)] border border-token text-ink rounded-full w-44 lg:w-56"
              />
            </div>

            {/* Region Filter */}
            <select
              value={selectedRegion}
              aria-label="Filter by region"
              onChange={(e) => {
                setSelectedRegion(e.target.value)
                setPage(1)
              }}
              className="pill-input text-xs py-1 px-2.5 bg-[var(--color-surface)] border border-token text-ink rounded-full cursor-pointer"
            >
              <option value="ALL">All Regions</option>
              <option value="Not provided">Region unavailable</option>
            </select>

            {/* Severity Filter */}
            <select
              value={selectedSeverity}
              aria-label="Filter by severity"
              onChange={(e) => {
                setSelectedSeverity(e.target.value)
                setPage(1)
              }}
              className="pill-input text-xs py-1 px-2.5 bg-[var(--color-surface)] border border-token text-ink rounded-full cursor-pointer"
            >
              <option value="ALL">All Severities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>

            {/* Risk Type Filter */}
            <select
              value={selectedRiskType}
              aria-label="Filter by risk type"
              onChange={(e) => {
                setSelectedRiskType(e.target.value)
                setPage(1)
              }}
              className="pill-input text-xs py-1 px-2.5 bg-[var(--color-surface)] border border-token text-ink rounded-full cursor-pointer"
            >
              <option value="ALL">All Risk Types</option>
              <option value="Stockout">Stockout</option>
              <option value="Expiry">Expiry</option>
              <option value="Excess">Excess</option>
            </select>
          </div>
        }
      >
        <DataTable
          columns={columns}
          data={paginatedPairs}
          loading={loading}
          error={error}
          onRetry={fetchData}
          onRowClick={(row) => setSelectedPair(row)}
          rowKey="pairId"
          sortKey={activeSort?.key}
          sortDir={activeSort?.dir}
          onSort={handleColumnSort}
          total={filteredPairs.length}
          page={page}
          pageSize={pageSize}
          onPageChange={(p) => setPage(p)}
          emptyTitle="No risk pairs match filters"
          emptyMessage="Try resetting filters or adjusting search keywords."
        />
      </SectionCard>

      {/* ── SKU–Destination Pair Detail Drawer ───────────────────────── */}
      <Drawer
        open={Boolean(selectedPair)}
        onClose={() => setSelectedPair(null)}
        title={selectedPair ? `${selectedPair.sku} at ${selectedPair.destination}` : 'Risk Details'}
        subtitle={`Rank #${selectedPair?.rank || '—'} · Region: ${selectedPair?.region || '—'}`}
      >
        {selectedPair && (
          <div className="space-y-6">
            {/* Status & Severity */}
            <div className="p-4 rounded-xl bg-[var(--color-tint)]/60 border border-token flex items-center justify-between">
              <div className="flex items-center gap-2">
                <SeverityChip severity={selectedPair.severity} />
                <span className="font-bold text-xs text-ink">{selectedPair.riskType} Risk</span>
              </div>
              <span className="font-mono text-xs text-muted">ID: {selectedPair.pairId}</span>
            </div>

            {/* Product Details */}
            <div className="p-4 rounded-xl border border-token bg-[var(--color-surface)]">
              <span className="text-[11px] text-muted block uppercase font-bold tracking-wider">
                SKU Information
              </span>
              <p className="text-sm font-bold text-ink mt-0.5">{selectedPair.sku}</p>
              <div className="flex items-center gap-4 mt-3 text-xs">
                <div>
                  <span className="text-muted block text-[11px]">Destination Hub</span>
                  <span className="font-semibold text-ink">{selectedPair.destination}</span>
                </div>
                <div>
                  <span className="text-muted block text-[11px]">Region</span>
                  <span className="font-semibold text-ink">{selectedPair.region}</span>
                </div>
                <div>
                  <span className="text-muted block text-[11px]">Cover (Days)</span>
                  <span className="font-mono font-bold text-danger">{selectedPair.daysOfCover} days</span>
                </div>
              </div>
            </div>

            {/* Rationale & Diagnosis */}
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider text-muted mb-1.5">
                Root Cause & Diagnosis
              </h4>
              <p className="text-sm text-ink leading-relaxed p-3.5 rounded-xl border border-token bg-[var(--color-surface)]">
                {selectedPair.rationale}
              </p>
            </div>

            {/* Drivers included in the risk response */}
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider text-muted mb-2">
                Risk Assessment Details
              </h4>
              <p className="text-sm text-ink leading-relaxed p-3.5 rounded-xl border border-token bg-[var(--color-surface)]">
                {selectedPair.drivers.primaryDriver || 'The API did not provide additional driver details.'}
              </p>
            </div>

            {/* Financial & Operational Exposure */}
            <div className="p-4 rounded-xl border border-token bg-[var(--color-tint)]/40 space-y-2">
              <h4 className="text-xs font-bold uppercase tracking-wider text-ink flex items-center gap-1.5">
                <AlertCircle className="w-4 h-4 text-warning" /> Reported Exposure
              </h4>
              <div className="flex items-center justify-between text-xs pt-1">
                <span className="text-muted">Expected Unmet Demand:</span>
                <span className="font-mono font-bold text-danger">
                  {(selectedPair.expectedUnmetDemand ?? 0).toLocaleString()} units
                </span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted">Expected Expiry Cost:</span>
                <span className="font-mono font-bold text-warning">
                  {(selectedPair.expectedExpiryLoss ?? 0).toLocaleString()} cost units
                </span>
              </div>
            </div>

            {/* Quick Action Navigation */}
            <div className="pt-2">
              <button
                onClick={() => {
                  setSelectedPair(null)
                  window.location.href = `/plan?sku=${selectedPair.sku}`
                }}
                className="pill-btn-primary w-full py-2.5 flex items-center justify-center gap-2 text-xs font-semibold shadow-sm"
              >
                <span>Generate Plan for {selectedPair.sku}</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}
      </Drawer>
    </PageLayout>
  )
}
