import { ArrowUpRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { Skeleton } from './Skeleton'
import { ErrorState } from './ErrorState'

/**
 * SectionCard — standard dashboard card with title, optional controls, arrow-link.
 *
 * Props:
 *   title        – card heading
 *   subtitle     – secondary text under title
 *   detailRoute  – react-router path for the arrow button (e.g. "/risk")
 *   controls     – React node rendered in the top-right (before the arrow)
 *   loading      – show card skeleton
 *   error        – show error state
 *   onRetry      – retry callback passed to ErrorState
 *   children     – card body content
 *   className
 *   bodyClassName
 */
export function SectionCard({
  title,
  subtitle,
  detailRoute,
  controls,
  loading = false,
  error = null,
  onRetry,
  children,
  className,
  bodyClassName,
}) {
  if (loading) {
    return (
      <div className={cn('card space-y-4', className)}>
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-40 w-full" />
      </div>
    )
  }

  if (error) {
    return (
      <div className={cn('card', className)}>
        <ErrorState error={error} onRetry={onRetry} />
      </div>
    )
  }

  return (
    <section className={cn('card flex flex-col', className)}>
      {/* Card header */}
      <div className="flex items-start justify-between gap-3 mb-4">
        <div className="min-w-0">
          <h2 className="text-[0.9375rem] font-semibold text-ink leading-snug truncate">{title}</h2>
          {subtitle && <p className="text-xs text-muted mt-0.5">{subtitle}</p>}
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {controls}
          {detailRoute && (
            <Link
              to={detailRoute}
              className="icon-btn-circle"
              aria-label={`Go to ${title} details`}
            >
              <ArrowUpRight className="w-3.5 h-3.5" aria-hidden="true" />
            </Link>
          )}
        </div>
      </div>

      {/* Card body */}
      <div className={cn('flex-1', bodyClassName)}>{children}</div>
    </section>
  )
}
