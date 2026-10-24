import { useState, useEffect, useCallback, useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Play,
  ArrowRight,
  ShieldAlert,
  Layers,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  Lock,
  ChevronRight,
} from 'lucide-react'
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  PieChart,
  Pie,
  Cell,
} from 'recharts'
import { getOverview, getDemandForecast, SKU_OPTIONS } from '@/services/overview'
import { StatCard } from '@/components/shared/StatCard'
import { SectionCard } from '@/components/shared/SectionCard'
import { ChartCard, ChartTooltip } from '@/components/shared/ChartCard'
import { StatusChip } from '@/components/shared/StatusChip'
import { SeverityChip } from '@/components/shared/SeverityChip'
import { CardSkeleton, TableSkeleton } from '@/components/shared/Skeleton'
import { ErrorState } from '@/components/shared/ErrorState'
import { DataTable } from '@/components/shared/DataTable'
import { PageLayout } from '@/components/shared/PageLayout'
import { cn, convertUsdToInr } from '@/lib/utils'

export default function Overview() {
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Demand Forecast controls
  const [selectedSku, setSelectedSku] = useState('')
  const [forecastSeries, setForecastSeries] = useState([])
  const [chartLoading, setChartLoading] = useState(false)
  const [chartError, setChartError] = useState(null)

  // Fetch overview data
  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await getOverview()
      setData(res)
    } catch (err) {
      setError(err?.message || 'Failed to load overview data')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])


  // Fetch demand forecast series
  useEffect(() => {
    let mounted = true
    async function loadChart() {
      setChartLoading(true)
      setChartError(null)
      try {
        const res = await getDemandForecast({ sku: selectedSku || null })
        if (mounted) setForecastSeries(res.series || [])
      } catch (err) {
        if (mounted) setChartError(err?.message || 'Failed to load forecast')
      } finally {
        if (mounted) setChartLoading(false)
      }
    }
    loadChart()
    return () => {
      mounted = false
    }
  }, [selectedSku])

  // Total risk count & breakdown calculation
  const riskMixData = useMemo(() => data?.riskMix || [], [data?.riskMix])
  const totalRiskCount = useMemo(() => {
    return riskMixData.reduce((acc, curr) => acc + (curr.value || 0), 0)
  }, [riskMixData])

  // Pipeline step definition mapped to backend pipeline stages
  const pipelineSteps = useMemo(() => {
    const pipeline = data?.pipeline || []
    const valStep = pipeline.find((p) => p.step === 'Validate')
    const fcastStep = pipeline.find((p) => p.step === 'Forecast')
    const planStep = pipeline.find((p) => p.step === 'Plan')
    const checkStep = pipeline.find((p) => p.step === 'Check')
    const backtestStep = pipeline.find((p) => p.step === 'Backtest')

    const isValidationBlocked = valStep?.status === 'ERROR_DATA'
    const displayTime = (step) => step?.completedAt
      ? `${new Date(step.completedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', timeZone: 'UTC' })} UTC`
      : '—'
    const statusLabel = (step, label) => step?.status == null || step.status === 'NOT_RUN'
      ? 'Not run'
      : label(step.status)
    const planStatusLabel = (status) => {
      const label = status === 'OPTIMAL' ? 'Feasible Schedule' : status
      return checkStep?.status === 'OK' ? `${label} · verified` : label
    }

    return [
      {
        id: 'validation',
        name: 'Data Validation',
        path: '/validation',
        status: valStep?.status || 'NOT_RUN',
        statusLabel: statusLabel(valStep, (status) => status === 'OK' ? 'Passed' : status),
        time: displayTime(valStep),
        blocked: false,
      },
      {
        id: 'forecast',
        name: 'Demand Forecast',
        path: '#demand-forecast',
        status: forecastSeries.length ? 'OK' : fcastStep?.status || 'NOT_RUN',
        statusLabel: forecastSeries.length
          ? 'Forecast loaded'
          : statusLabel(fcastStep, (status) => status === 'FALLBACK_FORECAST' ? 'Fallback Forecast' : status),
        time: displayTime(fcastStep),
        blocked: false,
      },
      {
        id: 'risk',
        name: 'Risk Assessment',
        path: '/risk',
        status: data?.riskMix ? 'OK' : 'NOT_RUN',
        statusLabel: data?.riskMix ? `${totalRiskCount} alerts` : 'Not run',
        time: '—',
        blocked: false,
      },
      {
        id: 'optimization',
        name: 'Distribution Plan',
        path: '/plan',
        status: planStep?.status || 'NOT_RUN',
        statusLabel: isValidationBlocked
          ? 'Blocked by Data'
          : statusLabel(planStep, planStatusLabel),
        time: displayTime(planStep),
        blocked: isValidationBlocked,
      },
      {
        id: 'backtest',
        name: 'Backtesting',
        path: '/backtest',
        status: backtestStep?.status || 'NOT_RUN',
        statusLabel: statusLabel(backtestStep, (status) => status === 'CHECK_FAILED' ? 'Check Failed' : status),
        time: displayTime(backtestStep),
        blocked: false,
      },
    ]
  }, [data?.pipeline, data?.riskMix, totalRiskCount, forecastSeries.length])

  // Top Actionable Alerts columns for DataTable
  const alertColumns = useMemo(
    () => [
      {
        key: 'severity',
        header: 'Severity',
        sortable: true,
        render: (val) => <SeverityChip severity={val} />,
      },
      {
        key: 'sku',
        header: 'SKU',
        sortable: true,
        render: (val) => <span className="font-mono text-xs font-bold text-ink">{val}</span>,
      },
      {
        key: 'type',
        header: 'Type',
        sortable: true,
        render: (val) => <span className="text-xs text-muted font-medium">{val}</span>,
      },
      {
        key: 'warehouse',
        header: 'Warehouse',
        sortable: true,
        render: (val) => <span className="text-xs font-mono text-ink">{val}</span>,
      },
      {
        key: 'message',
        header: 'Finding & Impact',
        render: (val) => <span className="text-xs text-ink">{val}</span>,
      },
      {
        key: 'action',
        header: 'Action',
        align: 'right',
        render: (_val, row) => (
          <Link
            to={row?.sku ? `/risk?sku=${encodeURIComponent(row.sku)}` : '/risk'}
            className="pill-btn-outline text-[11px] px-2.5 py-1 inline-flex items-center gap-1 hover:bg-[var(--color-primary)] hover:text-white transition-colors"
          >
            Inspect <ArrowRight className="w-3 h-3" />
          </Link>
        ),
      },
    ],
    []
  )

  if (error && !loading && !data) {
    return (
      <div className="max-w-7xl mx-auto py-12">
        <ErrorState error={new Error(error)} onRetry={loadData} />
      </div>
    )
  }

  const summaryCardsContent = loading && !data ? (
    Array.from({ length: 4 }).map((_, i) => <CardSkeleton key={i} />)
  ) : (
    <>
      {/* Metric 1: Latest Run & Solver Status */}
      <div className="card flex flex-col justify-between relative group hover:border-[var(--color-primary-lilac)] transition-colors">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-muted">
            Solver Status
          </span>
          <button
            onClick={() => navigate('/runs')}
            className="icon-btn-circle"
            title="View Run History"
            aria-label="View Run History"
          >
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
        <div className="my-2">
          <div className="flex items-center gap-2">
            <StatusChip status={data?.planStatus || 'NOT_RUN'} />
            {data?.lastRunId && <span className="font-mono text-xs text-muted">#{data.lastRunId}</span>}
          </div>
          <p className="text-xs text-muted mt-2">
            {data?.planStatus === 'OK'
              ? 'Optimal solution found within convergence tolerance'
              : data?.lastRunId
                ? `Run status: ${data?.planStatus}`
                : 'No planning run has been recorded yet.'}
          </p>
        </div>
        <div className="pt-2 border-t border-token flex items-center justify-between text-xs text-muted">
          <span>{data?.lastRunId ? `Pipeline run #${data.lastRunId}` : 'No pipeline run recorded'}</span>
          <Link to="/runs" className="text-primary hover:underline font-medium">
            Run history &rarr;
          </Link>
        </div>
      </div>

      {/* Metric 2: Unmet Demand */}
      <StatCard
        label="Unmet Demand"
        value={data?.metrics?.unmetDemand?.value}
        unit={data?.metrics?.unmetDemand?.unit || 'units'}
        delta={data?.metrics?.unmetDemand?.delta}
        deltaPositiveIsGood={data?.metrics?.unmetDemand?.deltaPositiveIsGood ?? false}
        deltaLabel="vs prev cycle"
        onNavigate={() => navigate('/risk')}
        loading={loading}
      />

      {/* Metric 3: Projected Expiry Loss */}
      <StatCard
        label="Projected Expiry Loss"
        prefix={data?.source === 'api' ? '' : '₹'}
        value={data?.source === 'api'
          ? data?.metrics?.expiryLoss?.value
          : convertUsdToInr(data?.metrics?.expiryLoss?.value)}
        unit={data?.metrics?.expiryLoss?.unit}
        delta={data?.metrics?.expiryLoss?.delta}
        deltaPositiveIsGood={data?.metrics?.expiryLoss?.deltaPositiveIsGood ?? false}
        deltaLabel="vs prev cycle"
        onNavigate={() => navigate('/risk')}
        loading={loading}
      />

      {/* Metric 4: Freight Cost */}
      <StatCard
        label="Freight Cost"
        prefix={data?.source === 'api' ? '' : '₹'}
        value={data?.source === 'api'
          ? data?.metrics?.freightCost?.value
          : convertUsdToInr(data?.metrics?.freightCost?.value)}
        unit={data?.metrics?.freightCost?.unit}
        delta={data?.metrics?.freightCost?.delta}
        deltaPositiveIsGood={data?.metrics?.freightCost?.deltaPositiveIsGood ?? false}
        deltaLabel="vs prev cycle"
        onNavigate={() => navigate('/plan')}
        loading={loading}
      />
    </>
  )

  const pageActions = (
    <div className="flex items-center gap-3">
      <span className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-primary/10 text-primary border border-token">
        <Sparkles className="w-3.5 h-3.5 text-primary" />
        Live Workspace
      </span>
      <Link
        to="/plan"
        className="pill-btn-primary px-4 py-2 flex items-center gap-2 font-semibold shadow-sm hover:scale-[1.02] transition-transform text-xs"
      >
        <Play className="w-3.5 h-3.5 fill-current" />
        <span>Run Planning Pipeline</span>
      </Link>
    </div>
  )

  return (
    <PageLayout
      actions={pageActions}
      summaryCards={summaryCardsContent}
    >

      {/* ── Pipeline Status Horizontal Stepper ──────────────────────── */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h2 className="text-base font-bold text-ink flex items-center gap-2">
              <Layers className="w-4 h-4 text-primary" />
              Planning Pipeline Sequence
            </h2>
            <p className="text-xs text-muted mt-0.5">
              End-to-end execution flow from raw data ingestion to production schedule dispatch.
            </p>
          </div>
          <span className="text-xs font-mono text-muted">5 stages configured</span>
        </div>

        {/* Stepper container */}
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3 relative">
          {pipelineSteps.map((step, idx) => {
            const isAnchor = step.path.startsWith('#')
            const content = (
              <>
                <div className="flex items-center justify-between mb-2">
                  <span className="w-5 h-5 rounded-full bg-[var(--color-tint)] text-primary font-bold text-xs flex items-center justify-center">
                    {idx + 1}
                  </span>
                  {step.blocked ? (
                    <span
                      className="chip chip-danger text-[10px] flex items-center gap-1"
                      title="Blocked: Resolve data validation errors first"
                    >
                      <Lock className="w-2.5 h-2.5" /> Blocked
                    </span>
                  ) : step.status === 'NOT_RUN' ? (
                    <span className="chip chip-neutral text-[10px]">Not run</span>
                  ) : step.status === 'CHECK_FAILED' ? (
                    <span className="chip chip-warning text-[10px] flex items-center gap-1">
                      <AlertTriangle className="w-2.5 h-2.5" /> Check Failed
                    </span>
                  ) : (
                    <span className="chip chip-success text-[10px] flex items-center gap-1">
                      <CheckCircle2 className="w-2.5 h-2.5" /> Done
                    </span>
                  )}
                </div>
                <h3 className="text-sm font-bold text-ink group-hover:text-primary transition-colors flex items-center justify-between">
                  <span>{step.name}</span>
                  <ChevronRight className="w-3.5 h-3.5 text-muted opacity-0 group-hover:opacity-100 transition-opacity" />
                </h3>
                <p className="text-xs text-muted mt-1">{step.statusLabel}</p>
                <span className="text-[10px] font-mono text-muted mt-3 block">{step.time}</span>
              </>
            )

            const linkClasses = cn(
              'flex flex-col p-3.5 rounded-2xl border transition-all relative group',
              step.blocked
                ? 'border-red-300 dark:border-red-900 bg-red-50/20 cursor-not-allowed opacity-75'
                : 'border-token bg-[var(--color-surface)] hover:border-[var(--color-primary-lilac)] hover:shadow-sm'
            )

            if (step.blocked) {
              return (
                <div key={step.id} className={linkClasses} aria-disabled="true">
                  {content}
                </div>
              )
            }

            if (isAnchor) {
              return (
                <a key={step.id} href={step.path} className={linkClasses}>
                  {content}
                </a>
              )
            }

            return (
              <Link key={step.id} to={step.path} className={linkClasses}>
                {content}
              </Link>
            )
          })}
        </div>
      </div>

      {/* ── Mid Section: Demand Forecast Card & Risk Mix Donut ───────── */}
      <div id="demand-forecast" className="grid grid-cols-1 lg:grid-cols-3 gap-6 scroll-mt-6">
        {/* Left 2 Cols: Demand Forecast Chart Card */}
        <div className="lg:col-span-2">
          <ChartCard
            title="Daily Demand Forecast"
            subtitle="7-day backend forecast; actual demand is not included in this response"
            chartHeight={270}
            controls={
              <div className="flex items-center gap-2">
                <label htmlFor="sku-select" className="text-xs text-muted">
                  Series:
                </label>
                <select
                  id="sku-select"
                  aria-label="Filter demand forecast by SKU series"
                  value={selectedSku}
                  onChange={(e) => setSelectedSku(e.target.value)}
                  className="pill-input text-xs py-1 px-3 bg-[var(--color-surface)] border border-token text-ink rounded-full cursor-pointer"
                >
                  {SKU_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
            }
          >
            {chartLoading ? (
              <div className="h-[270px] flex items-center justify-center">
                <TableSkeleton rows={4} cols={3} />
              </div>
            ) : chartError ? (
              <div className="h-[270px] flex items-center justify-center text-sm text-danger">
                {chartError}
              </div>
            ) : (
              <AreaChart data={forecastSeries} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="forecastAreaGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--color-primary-lilac)" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="var(--color-primary-lilac)" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--color-border)" />
                <XAxis
                  dataKey="week"
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
                  tickFormatter={(val) => `${val}`}
                />
                <Tooltip content={<ChartTooltip />} />
                {/* Shaded Upper/Lower Bounds */}
                <Area
                  type="monotone"
                  dataKey="upperBound"
                  stroke="transparent"
                  fill="var(--color-tint)"
                  fillOpacity={0.4}
                  name="Confidence Band"
                />
                <Area
                  type="monotone"
                  dataKey="forecast"
                  stroke="var(--color-primary)"
                  strokeWidth={2.5}
                  fill="url(#forecastAreaGrad)"
                  name="Forecast"
                />
                <Line
                  type="monotone"
                  dataKey="lowerBound"
                  stroke="var(--color-primary-lilac)"
                  strokeWidth={2}
                  dot={false}
                  name="Lower Bound"
                />
              </AreaChart>
            )}
          </ChartCard>
        </div>

        {/* Right 1 Col: Risk Mix Donut Card */}
        <div className="lg:col-span-1">
          <div className="card h-full flex flex-col justify-between p-6">
            <div className="flex items-center justify-between mb-2">
              <div>
                <h3 className="text-base font-bold text-ink flex items-center gap-2">
                  <ShieldAlert className="w-4 h-4 text-primary" />
                  Risk Breakdown
                </h3>
                <p className="text-xs text-muted mt-0.5">Distribution across primary failure modes</p>
              </div>
              <Link to="/risk" className="text-xs text-primary font-semibold hover:underline">
                Details &rarr;
              </Link>
            </div>

            {/* Donut with Center Count */}
            <div className="relative flex items-center justify-center my-4 h-[180px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Tooltip content={<ChartTooltip />} />
                  <Pie
                    data={riskMixData}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={55}
                    outerRadius={80}
                    paddingAngle={4}
                    stroke="none"
                  >
                    {riskMixData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>

              {/* Center Label */}
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                <span className="text-2xl font-bold text-ink leading-none">{totalRiskCount}</span>
                <span className="text-[11px] text-muted font-medium mt-1">Total Alerts</span>
              </div>
            </div>

            {/* Legend & Percent Breakdown */}
            <div className="space-y-2 pt-2 border-t border-token">
              {riskMixData.map((item) => (
                <div key={item.name} className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <span
                      className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                      style={{ background: item.color }}
                    />
                    <span className="text-muted font-medium">{item.name} Risk</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-ink">{item.value}</span>
                    <span className="text-muted text-[11px] w-9 text-right font-mono">
                      {totalRiskCount > 0 ? Math.round((item.value / totalRiskCount) * 100) : 0}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* ── Top Actionable Alerts Mini-Table (Refactored to DataTable) ─ */}
      <SectionCard
        title="Top Actionable Alerts"
        subtitle="Highest severity operational bottlenecks requiring immediate planner attention"
        detailRoute="/risk"
      >
        <DataTable
          columns={alertColumns}
          data={data?.topAlerts || []}
          loading={loading}
          error={error}
          onRetry={loadData}
          rowKey="alertId"
          emptyTitle="No alerts flagged"
          emptyMessage="No operational alerts detected for the current run."
        />
      </SectionCard>
    </PageLayout>
  )
}
