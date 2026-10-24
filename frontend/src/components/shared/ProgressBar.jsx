import { cn } from '@/lib/utils'

/**
 * ProgressBar component
 *
 * Props:
 *   value       – number (0–100) or null for indeterminate
 *   label       – string
 *   showValue   – boolean (default false)
 *   className   – string
 *   color       – string (default 'bg-[var(--color-primary)]')
 */
export function ProgressBar({
  value = null,
  label,
  showValue = false,
  className,
  color = 'bg-[var(--color-primary)]',
}) {
  const isIndeterminate = value === null || value === undefined
  const clampedValue = isIndeterminate ? 0 : Math.min(100, Math.max(0, value))

  return (
    <div className={cn('w-full flex flex-col gap-1.5', className)}>
      {(label || showValue) && (
        <div className="flex justify-between items-center text-xs">
          {label && <span className="font-medium text-ink">{label}</span>}
          {showValue && !isIndeterminate && (
            <span className="text-muted font-mono">{Math.round(clampedValue)}%</span>
          )}
        </div>
      )}
      <div className="h-2 w-full bg-[var(--color-tint)] rounded-full overflow-hidden relative">
        {isIndeterminate ? (
          <div
            className={cn('h-full w-2/5 rounded-full absolute', color)}
            style={{
              animation: 'indeterminate-bar 1.5s infinite ease-in-out',
            }}
          />
        ) : (
          <div
            className={cn('h-full rounded-full transition-all duration-300 ease-out', color)}
            style={{ width: `${clampedValue}%` }}
          />
        )}
      </div>
      <style>{`
        @keyframes indeterminate-bar {
          0% { left: -40%; }
          50% { left: 40%; width: 50%; }
          100% { left: 100%; width: 20%; }
        }
      `}</style>
    </div>
  )
}
