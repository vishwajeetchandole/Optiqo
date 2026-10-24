import { ArrowUpRight, TrendingUp, TrendingDown } from 'lucide-react'
import { cn, splitNumber, formatDelta } from '@/lib/utils'
import { Skeleton } from './Skeleton'
import { ErrorState } from './ErrorState'

/**
 * StatCard — metric card with large value, muted decimals, delta chip, arrow button.
 *
 * Props:
 *   label       – metric name
 *   value       – numeric value (or null while loading)
 *   decimals    – decimal places shown muted (default 0)
 *   delta       – numeric delta vs previous run (positive = good by default)
 *   deltaLabel  – override "vs prev run" text
 *   deltaPositiveIsGood – flip sentiment (default true)
 *   prefix      – string prepended before the value (e.g. "$")
 *   unit        – string appended after the value (e.g. "%")
 *   onNavigate  – callback for the arrow button (if omitted, button hidden)
 *   loading     – show skeleton
 *   error       – show error state
 */
export function StatCard({
  label,
  value,
  decimals = 0,
  delta,
  deltaLabel = 'vs prev run',
  deltaPositiveIsGood = true,
  prefix = '',
  unit = '',
  onNavigate,
  onClick,
  loading = false,
  error = null,
  className,
}) {
  if (loading) {
    return (
      <div className={cn('card space-y-3', className)}>
        <Skeleton className="h-3.5 w-28" />
        <Skeleton className="h-9 w-40" />
        <Skeleton className="h-3 w-24" />
      </div>
    )
  }

  if (error) {
    return (
      <div className={cn('card', className)}>
        <ErrorState error={error} />
      </div>
    )
  }

  const { integer, decimal } = splitNumber(value, decimals)
  const deltaStr = formatDelta(delta)
  const isPositive = delta != null && delta >= 0
  const isGood = deltaPositiveIsGood ? isPositive : !isPositive
  const DeltaIcon = isPositive ? TrendingUp : TrendingDown

  const deltaVariantClass = delta == null
    ? 'chip-neutral'
    : isGood
    ? 'chip-success'
    : 'chip-danger'

  const isInteractive = Boolean(onClick || onNavigate)
  const handleClick = onClick || onNavigate

  return (
    <div
      onClick={handleClick}
      className={cn(
        'card flex flex-col gap-2 relative group transition-all',
        isInteractive && 'card-interactive cursor-pointer',
        className
      )}
      tabIndex={isInteractive ? 0 : undefined}
      role={isInteractive ? 'button' : undefined}
      aria-label={isInteractive ? `View ${label} details` : undefined}
      onKeyDown={
        isInteractive
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                handleClick(e)
              }
            }
          : undefined
      }
    >
      {/* The card itself is the control, so its affordance stays visible without nesting buttons. */}
      {onNavigate && (
        <span
          className="icon-btn-circle absolute top-3 right-3 opacity-60 group-hover:opacity-100 group-hover:translate-x-0.5 transition-all"
          aria-hidden="true"
        >
          <ArrowUpRight className="w-3.5 h-3.5" />
        </span>
      )}

      {/* Label */}
      <p className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</p>

      {/* Value */}
      <p className="text-[2rem] font-bold leading-none text-ink tabular-nums" aria-label={`${label}: ${prefix}${integer}${decimal}${unit}`}>
        {prefix && <span className="text-muted text-xl mr-0.5">{prefix}</span>}
        {integer}
        {decimal && <span className="text-muted text-[1.375rem]">{decimal}</span>}
        {unit && <span className="text-muted text-lg ml-1">{unit}</span>}
      </p>

      {/* Delta */}
      {delta != null && (
        <p className="flex items-center gap-1.5 tabular-nums">
          <span className={cn('chip text-[0.7rem]', deltaVariantClass)}>
            <DeltaIcon className="w-3 h-3" aria-hidden="true" />
            {deltaStr}
          </span>
          <span className="text-xs text-muted">{deltaLabel}</span>
        </p>
      )}
    </div>
  )
}
