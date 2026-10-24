import { ResponsiveContainer } from 'recharts'
import { cn } from '@/lib/utils'
import { SectionCard } from './SectionCard'
import { Skeleton } from './Skeleton'

/**
 * Pill-style Recharts tooltip.
 * Use as <Tooltip content={<ChartTooltip />} /> in any Recharts chart.
 */
export function ChartTooltip({ active, payload, label, formatter }) {
  if (!active || !payload?.length) return null
  return (
    <div
      className="rounded-[var(--radius-pill)] border border-token bg-[var(--color-surface)] px-3 py-2 shadow-[var(--shadow-card)] text-xs"
    >
      {label && <p className="font-semibold text-ink mb-1">{label}</p>}
      {payload.map((entry, i) => (
        <p key={i} className="flex items-center gap-1.5">
          <span
            className="inline-block w-2 h-2 rounded-full flex-shrink-0"
            style={{ background: entry.color ?? entry.fill }}
          />
          <span className="text-muted">{entry.name}:</span>
          <span className="font-medium text-ink">
            {formatter ? formatter(entry.value, entry.name) : entry.value}
          </span>
        </p>
      ))}
    </div>
  )
}

/**
 * ChartCard — SectionCard wrapper sized for Recharts charts.
 *
 * Props: all SectionCard props, plus:
 *   chartHeight  – height of the ResponsiveContainer (default 240)
 *   legend       – React node rendered above the chart (e.g. PillTabs, PillSelect)
 *   loading      – show chart skeleton
 *   children     – Recharts chart JSX (BarChart, LineChart, etc.)
 */
export function ChartCard({
  title,
  subtitle,
  detailRoute,
  controls,
  chartHeight = 240,
  legend,
  loading = false,
  error = null,
  onRetry,
  children,
  className,
}) {
  if (loading) {
    return (
      <div className={cn('card space-y-4', className)}>
        <Skeleton className="h-4 w-32" />
        {legend && <Skeleton className="h-7 w-48" />}
        <Skeleton style={{ height: chartHeight }} className="w-full rounded-xl" />
      </div>
    )
  }

  return (
    <SectionCard
      title={title}
      subtitle={subtitle}
      detailRoute={detailRoute}
      controls={controls}
      error={error}
      onRetry={onRetry}
      className={className}
    >
      {legend && <div className="mb-3">{legend}</div>}
      <ResponsiveContainer width="100%" height={chartHeight}>
        {children}
      </ResponsiveContainer>
    </SectionCard>
  )
}
