import { useState, useEffect } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  Copy,
  Check,
  ShieldCheck,
  Truck,
  AlertTriangle,
  Building2,
  TrendingUp,
  Clock,
  Layers,
  Sparkles,
  ExternalLink,
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
} from 'recharts'
import { getPlanLine } from '@/services/plan'
import { ChartTooltip } from '@/components/shared/ChartCard'
import { StatusChip } from '@/components/shared/StatusChip'
import { Skeleton } from '@/components/shared/Skeleton'
import { EmptyState } from '@/components/shared/EmptyState'
import { ErrorState } from '@/components/shared/ErrorState'
import { PageLayout } from '@/components/shared/PageLayout'

export default function RecommendationDetail({
  lineId: propLineId,
  isDrawer = false,
  onClose: _onClose,
  onSelectLineId,
}) {
  const params = useParams()
  const lineId = propLineId || params.lineId
  const navigate = useNavigate()

  const [line, setLine] = useState(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)
  const [loadError, setLoadError] = useState(null)
  const [retryCount, setRetryCount] = useState(0)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    let mounted = true
    async function loadData() {
      if (!lineId) return
      setLoading(true)
      setNotFound(false)
      setLoadError(null)
      try {
        const res = await getPlanLine({ lineId })
        if (mounted) {
          if (!res) {
            setNotFound(true)
          } else {
            setLine(res)
          }
        }
      } catch (err) {
        if (mounted) setLoadError(err?.message || 'Failed to load recommendation details')
      } finally {
        if (mounted) setLoading(false)
      }
    }
    loadData()
    return () => {
      mounted = false
    }
  }, [lineId, retryCount])

  const handleCopyId = () => {
    if (!lineId) return
    navigator.clipboard.writeText(lineId)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleNavigateLine = (targetLineId) => {
    if (!targetLineId) return
    if (onSelectLineId) {
      onSelectLineId(targetLineId)
    } else {
      navigate(`/plan/${targetLineId}`)
    }
  }

  // Graceful 404 for unknown lineId
  if (notFound) {
    return (
      <div className="max-w-3xl mx-auto py-12 px-4">
        <EmptyState
          icon={AlertTriangle}
          title="Plan Line Not Found"
          message={`No dispatch recommendation exists with identifier "${lineId}". It may have been superseded or removed from the active plan.`}
          action={
            <Link to="/plan" className="pill-btn-primary text-xs px-4 py-2 mt-2 inline-flex items-center gap-1.5">
              <ArrowLeft className="w-3.5 h-3.5" /> Return to Distribution Plan
            </Link>
          }
        />
      </div>
    )
  }

  if (loadError) {
    return (
      <div className="max-w-3xl mx-auto py-12 px-4">
        <ErrorState
          error={new Error(loadError)}
          onRetry={() => setRetryCount((count) => count + 1)}
        />
      </div>
    )
  }

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="flex items-center justify-between">
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-6 w-24" />
        </div>
        <Skeleton className="h-28 w-full rounded-2xl" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Skeleton className="h-44 rounded-2xl" />
          <Skeleton className="h-44 rounded-2xl" />
        </div>
      </div>
    )
  }

  // Shared body content rendered in both drawer and standalone views
  const detailBody = (
    <div className="space-y-6">
      {/* ── Sub-toolbar in Drawer Mode ── */}
      {isDrawer && (
        <div className="flex items-center justify-between gap-2 pb-2 border-b border-token">
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs font-bold text-ink px-2.5 py-0.5 rounded-full bg-[var(--color-tint)] border border-token tabular-nums">
              {lineId}
            </span>
            <button
              onClick={handleCopyId}
              className="icon-btn-circle w-6 h-6 text-muted hover:text-ink"
              title="Copy Line ID"
              aria-label="Copy Line ID"
            >
              {copied ? <Check className="w-3 h-3 text-success" /> : <Copy className="w-3 h-3" />}
            </button>
            <span className="text-[11px] text-muted tabular-nums">
              {line?.navigation?.currentIndex} of {line?.navigation?.totalLines}
            </span>
          </div>

          <div className="flex items-center gap-1.5">
            <button
              onClick={() => handleNavigateLine(line?.navigation?.previousLineId)}
              disabled={!line?.navigation?.previousLineId}
              className="pill-btn-outline text-xs px-2 py-0.5 flex items-center gap-1 disabled:opacity-30 disabled:cursor-not-allowed"
              aria-label="Previous recommendation line"
            >
              <ChevronLeft className="w-3 h-3" /> Prev
            </button>
            <button
              onClick={() => handleNavigateLine(line?.navigation?.nextLineId)}
              disabled={!line?.navigation?.nextLineId}
              className="pill-btn-outline text-xs px-2 py-0.5 flex items-center gap-1 disabled:opacity-30 disabled:cursor-not-allowed"
              aria-label="Next recommendation line"
            >
              Next <ChevronRight className="w-3 h-3" />
            </button>
            <Link
              to={`/plan/${lineId}`}
              className="pill-btn-outline text-xs px-2.5 py-0.5 flex items-center gap-1 hover:text-primary"
              title="Open full page view"
            >
              <ExternalLink className="w-3 h-3" />
              <span>Full Page</span>
            </Link>
          </div>
        </div>
      )}

      {/* ── Header Card: SKU, Warehouse, Batch, Destination, Qty, Status ── */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 p-5 rounded-2xl bg-[var(--color-tint)]/60 border border-token">
        <div>
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className="font-mono text-xs font-bold text-ink px-2.5 py-0.5 rounded-full bg-[var(--color-surface)] border border-token tabular-nums">
              {line?.sku}
            </span>
            <span className="font-mono text-xs text-muted tabular-nums">Batch: {line?.batchId}</span>
            <StatusChip status={line?.status} size="sm" />
          </div>
          <h2 className="text-lg font-bold text-ink mt-2">{line?.description}</h2>
          <div className="flex items-center gap-3 mt-2 text-xs text-muted flex-wrap">
            <span className="flex items-center gap-1">
              <Truck className="w-3.5 h-3.5 text-primary" /> Origin: <strong>{line?.warehouse}</strong>
            </span>
            <span>&rarr;</span>
            <span className="flex items-center gap-1">
              <Building2 className="w-3.5 h-3.5 text-primary" /> Destination: <strong>{line?.destination}</strong>
            </span>
          </div>
        </div>

        <div className="text-left sm:text-right flex-shrink-0">
          <span className="text-[11px] text-muted block uppercase font-bold tracking-wider">
            Transfer Quantity
          </span>
          <p className="text-2xl font-bold font-mono text-ink tabular-nums">
            {line?.quantity?.toLocaleString()} <span className="text-sm text-muted">{line?.unit}</span>
          </p>
          <span className="text-xs text-muted font-mono mt-0.5 block tabular-nums">
            Freight: {line?.freightCost?.toLocaleString()} cost units
          </span>
        </div>
      </div>

      {/* ── One-Sentence Explanation (Backend verifier, PRD P0-08) ── */}
      <div className="p-4 rounded-2xl border border-[var(--color-primary-lilac)]/30 bg-[var(--color-surface)] space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold uppercase tracking-wider text-primary flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5 text-primary" /> Optimization Explanation
          </span>
          {line?.explanationVerified && (
            <span
              className="chip chip-success text-[10px] flex items-center gap-1 font-bold"
              title="Explanation verifier checked against solver invariant constraints"
            >
              <ShieldCheck className="w-3 h-3 text-emerald-600" />
              Verified (PRD P0-08)
            </span>
          )}
        </div>
        <p className="text-sm text-ink leading-relaxed font-medium">
          "{line?.explanation}"
        </p>
      </div>

      {/* ── Evidence Cards Grid ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Evidence Card 1: Forecast with Confidence Range */}
        <div className="card p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-bold uppercase tracking-wider text-muted flex items-center gap-1.5">
              <TrendingUp className="w-3.5 h-3.5 text-primary" /> Destination Forecast Horizon
            </span>
            <span className="text-[10px] font-mono text-muted tabular-nums">Arrival: {line?.arrivalDate}</span>
          </div>
          <p className="text-xs text-muted mb-2">
            Backend forecast mean and range for this destination-SKU pair.
          </p>
          <div className="h-32 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={line?.forecastEvidence || []} margin={{ top: 5, right: 5, left: -25, bottom: 0 }}>
                <CartesianGrid strokeDasharray="2 2" vertical={false} stroke="var(--color-border)" />
                <XAxis dataKey="period" stroke="var(--color-muted)" fontSize={10} tickLine={false} axisLine={false} />
                <YAxis stroke="var(--color-muted)" fontSize={10} tickLine={false} axisLine={false} />
                <Tooltip content={<ChartTooltip />} />
                <Area type="monotone" dataKey="high" stroke="transparent" fill="var(--color-tint)" fillOpacity={0.6} name="High Bound" />
                <Area type="monotone" dataKey="mid" stroke="var(--color-primary)" strokeWidth={2} fill="var(--color-primary-lilac)" fillOpacity={0.15} name="Mid Forecast" />
                <Line type="monotone" dataKey="low" stroke="var(--color-muted)" strokeDasharray="3 3" dot={false} name="Low Bound" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Evidence Card 2: Current & Inbound Stock vs Selected Quantity */}
        <div className="card p-4 flex flex-col justify-between">
          <div>
            <span className="text-xs font-bold uppercase tracking-wider text-muted flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-primary" /> Stock & Balance Evidence
            </span>
            <div className="grid grid-cols-2 gap-3 mt-3 text-xs">
              <div className="p-3 rounded-xl border border-token bg-[var(--color-surface)]">
                <span className="text-muted block text-[11px]">Destination Stock</span>
                <span className="font-mono text-sm font-bold text-ink tabular-nums">
                  {line?.stockEvidence?.currentDestinationStock?.toLocaleString() ?? '—'} {line?.unit}
                </span>
              </div>
              <div className="p-3 rounded-xl border border-token bg-[var(--color-surface)]">
                <span className="text-muted block text-[11px]">Inbound Stock</span>
                <span className="font-mono text-sm font-bold text-danger tabular-nums">
                  {line?.stockEvidence?.inboundDestination?.toLocaleString() ?? '—'} {line?.unit}
                </span>
              </div>
            </div>
          </div>
          <p className="text-[11px] text-muted mt-3">
            Selected shipment: {line?.stockEvidence?.shippedQuantity?.toLocaleString() ?? line?.quantity?.toLocaleString()} {line?.unit}
          </p>
        </div>

        {/* Evidence Card 3: Remaining Shelf Life vs SKU Minimum */}
        <div className="card p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-muted flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-primary" /> Shelf-Life Invariant
            </span>
            <span className={`chip text-[10px] font-bold ${
              (line?.shelfLifeEvidence?.remainingAtArrivalDays ?? 0) >=
                (line?.shelfLifeEvidence?.skuMinimumDays ?? Infinity)
                ? 'chip-success'
                : 'chip-danger'
            }`}>
              {(line?.shelfLifeEvidence?.remainingAtArrivalDays ?? 0) >=
                (line?.shelfLifeEvidence?.skuMinimumDays ?? Infinity)
                ? 'In Compliance'
                : 'Not Verified'}
            </span>
          </div>
          <div className="my-3">
            <div className="flex items-baseline justify-between mb-1 text-xs">
              <span className="text-ink font-semibold tabular-nums">
                {line?.shelfLifeEvidence?.remainingAtArrivalDays} days remaining
              </span>
              <span className="text-muted font-mono tabular-nums">
                Min required: {line?.shelfLifeEvidence?.skuMinimumDays} days
              </span>
            </div>
            <div className="w-full bg-[var(--color-tint)] h-3 rounded-full relative overflow-hidden">
              <div
                className="bg-emerald-500 h-full rounded-full transition-all duration-500"
                style={{
                  width: `${Math.min(
                    100,
                    ((line?.shelfLifeEvidence?.remainingAtArrivalDays ?? 0) /
                      Math.max(1, line?.shelfLifeEvidence?.skuMinimumDays ?? 1)) * 100
                  )}%`,
                }}
              />
              <div
                className="absolute top-0 bottom-0 w-1 bg-red-400 shadow"
                style={{
                  left: `${Math.min(
                    100,
                    ((line?.shelfLifeEvidence?.skuMinimumDays ?? 0) /
                      Math.max(1, line?.shelfLifeEvidence?.remainingAtArrivalDays ?? 1)) * 100
                  )}%`,
                }}
                title="Minimum required shelf life"
              />
            </div>
          </div>
          <p className="text-[11px] text-muted">
            Shelf-life requirement values are provided by the backend verifier.
          </p>
        </div>

        {/* Evidence Card 4: Backend-provided next-best alternative */}
        <div className="card p-4 flex flex-col justify-between">
          <span className="text-xs font-bold uppercase tracking-wider text-muted flex items-center gap-1.5">
            <Building2 className="w-3.5 h-3.5 text-primary" /> Counterfactual Alternative
          </span>
          {line?.nextBestAlternative ? (
            <div className="my-2 space-y-2 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-muted">Next-best warehouse:</span>
                <span className="font-semibold text-ink">{line.nextBestAlternative.warehouse}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted">Alternative freight cost:</span>
                <span className="font-mono text-ink tabular-nums">
                  {line.nextBestAlternative.cost?.toLocaleString() ?? '—'} cost units
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted">Selected freight cost:</span>
                <span className="font-mono text-ink tabular-nums">
                  {line.nextBestAlternative.selectedCost?.toLocaleString() ?? '—'} cost units
                </span>
              </div>
            </div>
          ) : (
            <p className="text-xs text-muted mt-3">
              No next-best warehouse cost was returned for this shipment line.
            </p>
          )}
        </div>
      </div>

      {/* ── Backend Checker Result ── */}
      <div className="pt-2 flex items-center justify-between border-t border-token text-xs text-muted">
        <span className="font-mono tabular-nums">
          {line?.explanationVerified
            ? 'The independent plan checker passed.'
            : 'Independent checker result unavailable or failed.'}
        </span>
        {!isDrawer && (
          <Link to="/plan" className="pill-btn-outline text-xs px-3 py-1.5 flex items-center gap-1.5">
            <ArrowLeft className="w-3.5 h-3.5" /> Back to Full Plan
          </Link>
        )}
      </div>
    </div>
  )

  // Drawer embedding mode: Render direct contents
  if (isDrawer) {
    return detailBody
  }

  // Standalone Page View: Wrap in PageLayout
  return (
    <PageLayout
      title={`Transfer Recommendation ${line?.lineId || lineId || ''}`}
      subtitle={`SKU: ${line?.sku || '...'} · ${line?.description || 'Multi-echelon re-balancing dispatch line'}`}
      actions={
        <div className="flex items-center gap-2 flex-wrap">
          <Link
            to="/plan"
            className="pill-btn-outline text-xs px-3 py-1.5 flex items-center gap-1.5"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Distribution Plan</span>
          </Link>
          <button
            onClick={handleCopyId}
            className="pill-btn-outline text-xs px-3 py-1.5 flex items-center gap-1.5"
            title="Copy Line ID"
          >
            {copied ? <Check className="w-3 h-3 text-success" /> : <Copy className="w-3 h-3" />}
            <span className="font-mono tabular-nums">{lineId}</span>
          </button>
          <div className="flex items-center gap-1">
            <button
              onClick={() => handleNavigateLine(line?.navigation?.previousLineId)}
              disabled={!line?.navigation?.previousLineId}
              className="pill-btn-outline text-xs px-2.5 py-1.5 flex items-center gap-1 disabled:opacity-30 disabled:cursor-not-allowed"
              aria-label="Previous recommendation line"
            >
              <ChevronLeft className="w-3 h-3" /> Prev
            </button>
            <button
              onClick={() => handleNavigateLine(line?.navigation?.nextLineId)}
              disabled={!line?.navigation?.nextLineId}
              className="pill-btn-outline text-xs px-2.5 py-1.5 flex items-center gap-1 disabled:opacity-30 disabled:cursor-not-allowed"
              aria-label="Next recommendation line"
            >
              Next <ChevronRight className="w-3 h-3" />
            </button>
          </div>
        </div>
      }
    >
      <div className="max-w-4xl mx-auto bg-[var(--color-surface)] border border-token rounded-3xl p-6 md:p-8 shadow-sm">
        {detailBody}
      </div>
    </PageLayout>
  )
}
