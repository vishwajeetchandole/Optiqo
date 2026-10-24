import { PackageSearch } from 'lucide-react'
import { cn } from '@/lib/utils'

/**
 * EmptyState — shown when a list / table has no data.
 * Props:
 *   icon      – Lucide icon component (default PackageSearch)
 *   title     – main text
 *   message   – secondary text
 *   action    – optional React node (e.g. a button)
 *   className
 */
export function EmptyState({
  icon: Icon = PackageSearch,
  title = 'Nothing here yet',
  message = 'Data will appear once available.',
  action,
  className,
}) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-3 py-16 px-6 text-center',
        className
      )}
    >
      <span
        className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-tint"
        aria-hidden="true"
      >
        <Icon className="w-6 h-6 text-primary" strokeWidth={1.5} />
      </span>
      <p className="text-[0.9375rem] font-600 text-ink">{title}</p>
      <p className="text-sm text-muted max-w-xs">{message}</p>
      {action && <div className="mt-1">{action}</div>}
    </div>
  )
}
