import { cn } from '@/lib/utils'

/**
 * Skeleton — animated shimmer placeholder.
 * Props:
 *   className  – extra Tailwind classes (control width / height here)
 *   count      – repeat N times (default 1)
 *   gap        – gap between repeated skeletons (default 'gap-2')
 */
export function Skeleton({ className, count = 1, gap = 'gap-2' }) {
  if (count === 1) {
    return <div className={cn('skeleton h-4 w-full rounded', className)} aria-hidden="true" />
  }
  return (
    <div className={cn('flex flex-col', gap)} aria-hidden="true">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className={cn('skeleton h-4 w-full rounded', className)} />
      ))}
    </div>
  )
}

/**
 * CardSkeleton — full card-shaped skeleton used while a SectionCard loads.
 */
export function CardSkeleton({ className }) {
  return (
    <div className={cn('card space-y-3', className)} aria-hidden="true">
      <Skeleton className="h-4 w-1/3" />
      <Skeleton className="h-8 w-2/3" />
      <Skeleton className="h-3 w-1/2" />
    </div>
  )
}

/**
 * TableSkeleton — skeleton rows for DataTable.
 */
export function TableSkeleton({ rows = 5, cols = 4 }) {
  return (
    <div className="space-y-2" aria-hidden="true">
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="flex gap-4">
          {Array.from({ length: cols }).map((_, c) => (
            <Skeleton key={c} className="h-5 flex-1" />
          ))}
        </div>
      ))}
    </div>
  )
}
