import { AlertTriangle, RefreshCw } from 'lucide-react'
import { cn } from '@/lib/utils'

/**
 * ErrorState — shown when a data fetch fails.
 * Props:
 *   error     – Error object (optional, shows message if present)
 *   onRetry   – callback to retry the fetch
 *   className
 */
export function ErrorState({ error, onRetry, className }) {
  const message = error?.message ?? 'Something went wrong. Please try again.'
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-3 py-16 px-6 text-center',
        className
      )}
      role="alert"
    >
      <span
        className="inline-flex items-center justify-center w-14 h-14 rounded-full"
        style={{ background: 'var(--color-danger-bg)' }}
        aria-hidden="true"
      >
        <AlertTriangle className="w-6 h-6" style={{ color: 'var(--color-danger-text)' }} strokeWidth={1.5} />
      </span>
      <p className="text-[0.9375rem] font-semibold text-ink">Failed to load</p>
      <p className="text-sm text-muted max-w-xs">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="btn-pill btn-ghost mt-1 flex items-center gap-1.5"
          aria-label="Retry"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Retry
        </button>
      )}
    </div>
  )
}
