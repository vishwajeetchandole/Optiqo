import { useState, useEffect, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  Play,
  RotateCw,
  Calendar,
  FileCode,
} from 'lucide-react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts'
import { getBacktestSummary, runBacktestWithProgress } from '@/services/backtest'
import { SectionCard } from '@/components/shared/SectionCard'
import { ChartCard, ChartTooltip } from '@/components/shared/ChartCard'
import { ProgressBar } from '@/components/shared/ProgressBar'
import { PageLayout } from '@/components/shared/PageLayout'
import { Skeleton } from '@/components/shared/Skeleton'
import { ErrorState } from '@/components/shared/ErrorState'
import { EmptyState } from '@/components/shared/EmptyState'
import { cn, CHART_COLORS } from '@/lib/utils'

export default function Backtesting() {
  const [searchParams, setSearchParams] = useSearchParams()
  const initialWindow = searchParams.get('window') || '8w'
  const initialSeed = searchParams.get('seed') ? Number(searchParams.get('seed')) : 42

  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Evaluation controls initialized from search params
  const [windowSelection, setWindowSelection] = useState(initialWindow)
  const [seedValue, setSeedValue] = useState(initialSeed)

  // Sync to URL search params
  useEffect(() => {
    const params = new URLSearchParams()
    if (windowSelection !== '8w') params.set('window', windowSelection)
    if (seedValue !== 42) params.set('seed', String(seedValue))
    setSearchParams(params, { replace: true })
  }, [windowSelection, seedValue, setSearchParams])

  // Run states: 'idle' | 'running' | 'done' | 'failed'
  const [runState, setRunState] = useState('idle')
  const [progressPercent, setProgressPercent] = useState(0)
  const [progressStage, setProgressStage] = useState('')

  const gainDecompositionData = data?.gainDecomposition || []

  const loadSummary = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await getBacktestSummary()
      setData(res)
    } catch (err) {
      setError(err?.message || 'Failed to load backtest evaluation')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadSummary()
  }, [loadSummary])



  // Run backtest with progress orchestration
  const handleRunBacktest = async () => {
    setRunState('running')
    setProgressPercent(15)
    setProgressStage('Initializing rolling simulation engine...')

    try {
      const res = await runBacktestWithProgress({
        window: windowSelection,
        seed: Number(seedValue),
        onProgress: (stage, percent) => {
          setProgressStage(stage)
          setProgressPercent(percent)
        },
      })
      setData(res)
      setRunState('done')
    } catch (err) {
      setError(err?.message || 'Backtesting execution failed')
      setRunState('failed')
    } finally {
      setTimeout(() => {
        setRunState('idle')
        setProgressPercent(0)
      }, 700)
    }
  }

  const sectionNavLinks = (
    <div className="flex items-center gap-2 overflow-x-auto py-1 text-xs">
      <a
        href="#kpis"
        className="px-3 py-1 rounded-full border border-token/80 bg-surface text-muted hover:text-primary hover:border-primary transition-colors whitespace-nowrap"
      >
        K1–K8 Evaluation
      </a>
      <a
        href="#decomposition"
        className="px-3 py-1 rounded-full border border-token/80 bg-surface text-muted hover:text-primary hover:border-primary transition-colors whitespace-nowrap"
      >
        Gain Decomposition
      </a>
      <a
        href="#daily-trajectory"
        className="px-3 py-1 rounded-full border border-token/80 bg-surface text-muted hover:text-primary hover:border-primary transition-colors whitespace-nowrap"
      >
        Daily Trajectories
      </a>
      <a
        href="#audit-report"
        className="px-3 py-1 rounded-full border border-token/80 bg-surface text-muted hover:text-primary hover:border-primary transition-colors whitespace-nowrap"
      >
        Audit Manifest
      </a>
    </div>
  )

  const backtestControls = (
    <div className="flex items-center flex-wrap gap-2.5">
      {/* Evaluation Window Selector */}
      <div className="flex items-center gap-1.5 bg-surface border border-token px-3 py-1.5 rounded-full text-xs text-ink">
        <Calendar className="w-3.5 h-3.5 text-muted" />
        <select
          value={windowSelection}
          onChange={(e) => setWindowSelection(e.target.value)}
          className="bg-transparent font-medium text-ink text-xs focus:outline-none cursor-pointer"
          aria-label="Evaluation Window"
        >
          <option value="8w">8 Weeks</option>
          <option value="12w">12 Weeks</option>
          <option value="16w">16 Weeks</option>
        </select>
      </div>

      {/* Random Seed Number Input */}
      <div className="flex items-center gap-1.5 bg-surface border border-token px-3 py-1.5 rounded-full text-xs text-ink">
        <span className="text-muted font-mono">Seed:</span>
        <input
          type="number"
          value={seedValue}
          onChange={(e) => setSeedValue(e.target.value)}
          className="w-12 bg-transparent font-mono font-bold text-ink text-xs focus:outline-none tabular-nums"
          aria-label="Random Seed"
        />
      </div>

      {/* Primary "Run Backtest" Button */}
      <button
        onClick={handleRunBacktest}
        disabled={runState === 'running'}
        className="pill-btn-primary text-xs px-4 py-2 flex items-center gap-2 font-semibold shadow-sm"
      >
        <Play className={cn('w-3.5 h-3.5 fill-current', runState === 'running' && 'animate-spin')} />
        <span>{runState === 'running' ? 'Running Backtest...' : 'Run Backtest'}</span>
      </button>
    </div>
  )

  return (
    <PageLayout
      actions={backtestControls}
      sectionNav={sectionNavLinks}
    >

      {/* ── Staged Running State Progress Bar ─────────────────────────── */}
      {runState === 'running' && (
        <div className="card p-5 border-[var(--color-primary-lilac)]/40 bg-[var(--color-tint)]/40 space-y-3 animate-fadeIn">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <RotateCw className="w-4 h-4 text-primary animate-spin" />
              <span className="font-bold text-sm text-ink">{progressStage}</span>
            </div>
            <span className="font-mono text-xs text-muted">{progressPercent}%</span>
          </div>
          <ProgressBar value={progressPercent} />
          <p className="text-[11px] text-muted">The backend is processing the policy comparison.</p>
        </div>
        )}

      {error && !data ? (
        <ErrorState
          title="Failed to Load Backtest Evaluation"
          message={error}
          onRetry={() => loadSummary()}
        />
      ) : loading && !data ? (
        <div className="space-y-6">
          <Skeleton className="h-64 rounded-3xl" />
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <Skeleton className="h-72 rounded-3xl" />
            <Skeleton className="h-72 lg:col-span-2 rounded-3xl" />
          </div>
        </div>
      ) : !data ? (
        <EmptyState
          title="No backtest results yet"
          message="Run a policy comparison to calculate and save evaluation metrics."
          action={
            <button
              onClick={handleRunBacktest}
              disabled={runState === 'running'}
              className="pill-btn-primary text-xs px-4 py-2"
            >
              Run backtest
            </button>
          }
        />
      ) : (
        <>
          {/* ── PRD K1–K8 Policy Comparison Table ────────────────────────── */}
          <div id="kpis">
            <SectionCard
              title="KPI Policy Evaluation Comparison (PRD K1–K8)"
              subtitle="Side-by-side performance of Static Heuristic (B1), Reactive Min-Max (B2), and Optiqo multi-echelon optimization."
            >
              <div className="overflow-x-auto rounded-2xl border border-token">
                <table className="w-full border-collapse text-sm">
                  <thead>
                    <tr className="table-header-pill">
                      <th className="px-4 py-2.5 text-left font-bold">Metric (PRD)</th>
                      <th className="px-4 py-2.5 text-left font-bold">Threshold Target</th>
                      <th className="px-4 py-2.5 text-right font-bold">B1 (Static)</th>
                      <th className="px-4 py-2.5 text-right font-bold">B2 (Reactive)</th>
                      {/* Highlighted Optiqo Column */}
                      <th className="px-4 py-2.5 text-right font-bold bg-[var(--color-primary)] text-white">
                        Optiqo
                      </th>
                      <th className="px-4 py-2.5 text-right font-bold">Difference vs B2 (Abs)</th>
                      <th className="px-4 py-2.5 text-right font-bold">Difference vs B2 (%)</th>
                      <th className="px-4 py-2.5 text-center font-bold">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(data?.kpis || []).map((kpi, idx) => (
                      <tr
                        key={kpi.id}
                        className={cn(
                          'border-t border-token hover:bg-[var(--color-tint)] transition-colors',
                          idx % 2 === 1 && 'bg-[var(--color-surface)]'
                        )}
                      >
                        {/* KPI Name */}
                        <td className="px-4 py-2.5 font-medium text-xs text-ink">
                          <div className="flex items-center gap-1.5">
                            <span className="font-mono text-[10px] text-muted">{kpi.id}</span>
                            <span>{kpi.name}</span>
                          </div>
                        </td>

                        {/* Threshold */}
                        <td className="px-4 py-2.5 font-mono text-xs text-muted tabular-nums">
                          {kpi.threshold}
                        </td>

                        {/* B1 Value */}
                        <td className="px-4 py-2.5 font-mono text-xs text-right text-muted tabular-nums">
                          {`${kpi.b1.toLocaleString()} ${kpi.unit}`}
                        </td>

                        {/* B2 Value */}
                        <td className="px-4 py-2.5 font-mono text-xs text-right text-ink font-semibold tabular-nums">
                          {`${kpi.b2.toLocaleString()} ${kpi.unit}`}
                        </td>

                        {/* Highlighted Optiqo Value */}
                        <td className="px-4 py-2.5 font-mono text-xs text-right font-bold text-primary bg-[var(--color-tint)]/60 tabular-nums">
                          {`${kpi.optiqo.toLocaleString()} ${kpi.unit}`}
                        </td>

                        {/* Difference vs B2 (Absolute) — Neutral wording */}
                        <td className="px-4 py-2.5 font-mono text-xs text-right text-ink tabular-nums">
                          {kpi.diffVsB2Abs == null
                            ? '—'
                            : `${kpi.diffVsB2Abs > 0 ? '+' : ''}${kpi.diffVsB2Abs.toLocaleString()} ${kpi.unit}`}
                        </td>

                        {/* Difference vs B2 (Relative %) — Neutral wording */}
                        <td className="px-4 py-2.5 font-mono text-xs text-right tabular-nums">
                          <span
                            className={cn(
                              'chip text-[11px] font-bold font-mono',
                              kpi.b2BeatStatus === 'MET'
                                ? 'chip-success'
                                : kpi.b2BeatStatus === 'NOT_EVALUATED' ? 'chip-neutral' : 'chip-danger'
                            )}
                          >
                            {kpi.diffVsB2Rel == null
                              ? 'Not evaluated'
                              : `${kpi.diffVsB2Rel > 0 ? '+' : ''}${kpi.diffVsB2Rel}%`}
                          </span>
                        </td>

                        {/* Met / Not Met Chip (Derived ONLY from API response) */}
                        <td className="px-4 py-2.5 text-center">
                          <span
                            className={cn(
                              'chip text-[10px] font-bold',
                              kpi.thresholdStatus === 'MET'
                                ? 'chip-success'
                                : kpi.thresholdStatus === 'NOT_EVALUATED' ? 'chip-neutral' : 'chip-danger'
                            )}
                          >
                            {kpi.thresholdStatus === 'MET'
                              ? 'Met'
                              : kpi.thresholdStatus === 'NOT_EVALUATED' ? 'Not evaluated' : 'Not met'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </SectionCard>
          </div>

          {/* ── Mid Section: Gain Decomposition & Daily Metrics Charts ───── */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left 1 Col: Gain Decomposition Card (Waterfall / Stacked Style) */}
            <div id="decomposition" className="lg:col-span-1">
              <ChartCard
                title="Gain Decomposition Analysis"
                subtitle="Backend-reported cost effects (cost units)"
                chartHeight={270}
              >
                <BarChart
                  data={gainDecompositionData}
                  margin={{ top: 10, right: 10, left: -10, bottom: 20 }}
                >
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--color-border)" />
                  <XAxis
                    dataKey="name"
                    stroke="var(--color-muted)"
                    fontSize={9}
                    interval={0}
                    angle={-15}
                    textAnchor="end"
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis
                    stroke="var(--color-muted)"
                    fontSize={10}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(value) => Number(value).toLocaleString()}
                  />
                  <Tooltip content={<ChartTooltip />} />
                  <Bar dataKey="value" fill={CHART_COLORS.violet} radius={[4, 4, 0, 0]} name="Cost effect" />
                </BarChart>
              </ChartCard>
            </div>

            {/* Right 2 Cols: Daily Evaluation Charts (PillTabs for Metric) */}
            <div id="daily-trajectory" className="lg:col-span-2">
              <ChartCard
                title="Daily Policy Trajectory"
                subtitle="Daily time-series data is not included in the backend response."
                chartHeight={270}
              >
                <EmptyState
                  title="Daily metrics are unavailable"
                  message="This backend contract returns aggregate KPI comparisons, not daily trajectories."
                />
              </ChartCard>
            </div>
          </div>
        </>
      )}

      {/* ── Report Footer (PRD 16.4 Requirement) ──────────────────────── */}
      <div id="audit-report" className="card p-5 border-token bg-[var(--color-tint)]/30 space-y-3 text-xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-token pb-2">
          <div className="flex items-center gap-2">
            <FileCode className="w-4 h-4 text-primary" />
            <span className="font-bold text-ink uppercase tracking-wider text-[11px]">
              Backtesting Audit Trail & System Parameters (PRD 16.4)
            </span>
          </div>
          <span className="chip chip-warning font-mono font-bold text-[10px]">
            {data?.systemMetadata?.dataset || 'Dataset unavailable'}
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-muted">
          <div>
            <span className="block text-[10px] uppercase font-bold text-muted">Random Seed</span>
            <span className="font-mono font-bold text-ink tabular-nums">{data?.seed ?? '—'}</span>
          </div>
          <div>
            <span className="block text-[10px] uppercase font-bold text-muted">Evaluation Window</span>
            <span className="font-mono font-bold text-ink tabular-nums">{data?.evaluationWindow || '—'}</span>
          </div>
          <div>
            <span className="block text-[10px] uppercase font-bold text-muted">Solver & MIP Engine</span>
            <span className="font-mono text-ink text-[11px] block">{data?.systemMetadata?.solverVersion}</span>
            <span className="font-mono text-[10px] text-muted block">{data?.systemMetadata?.underlyingMip}</span>
          </div>
          <div>
            <span className="block text-[10px] uppercase font-bold text-muted">Execution Timestamp</span>
            <span className="font-mono text-ink tabular-nums">{data?.timestamp || '—'}</span>
          </div>
        </div>
      </div>
    </PageLayout>
  )
}
