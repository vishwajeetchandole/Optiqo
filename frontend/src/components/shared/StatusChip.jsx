import { cn } from '@/lib/utils'

/**
 * StatusChip — shows OK / SOLVER_TIMEOUT / SOLVER_NOT_OPTIMAL /
 *              INFEASIBLE / CHECK_FAILED / ERROR_DATA / FALLBACK_FORECAST
 *              and generic success / warning / danger / neutral variants.
 *
 * Props:
 *   status   – one of the PRD status codes or 'success'|'danger'|'warning'|'neutral'
 *   label    – override display text (defaults to a prettified status)
 *   size     – 'sm' | 'md' (default 'md')
 *   dot      – show coloured dot prefix (default false)
 */

const STATUS_MAP = {
  // PRD solver status codes
  OK:                  { variant: 'success',  label: 'OK' },
  SOLVER_TIMEOUT:      { variant: 'warning',  label: 'Solver timeout' },
  SOLVER_NOT_OPTIMAL:  { variant: 'warning',  label: 'Not optimal' },
  INFEASIBLE:          { variant: 'danger',   label: 'Infeasible' },
  CHECK_FAILED:        { variant: 'danger',   label: 'Check failed' },
  ERROR_DATA:          { variant: 'danger',   label: 'Data error' },
  FALLBACK_FORECAST:   { variant: 'warning',  label: 'Fallback forecast' },
  // Generic
  success:             { variant: 'success',  label: 'Success' },
  danger:              { variant: 'danger',   label: 'Error' },
  warning:             { variant: 'warning',  label: 'Warning' },
  neutral:             { variant: 'neutral',  label: 'Neutral' },
  primary:             { variant: 'primary',  label: 'Info' },
}

const VARIANT_CLASSES = {
  success: 'chip-success',
  danger:  'chip-danger',
  warning: 'chip-warning',
  neutral: 'chip-neutral',
  primary: 'chip-primary',
}

const DOT_CLASSES = {
  success: 'bg-[var(--color-success-text)]',
  danger:  'bg-[var(--color-danger-text)]',
  warning: 'bg-[var(--color-warning-text)]',
  neutral: 'bg-[var(--color-neutral-text)]',
  primary: 'bg-[var(--color-primary)]',
}

export function StatusChip({ status = 'neutral', label, size = 'md', dot = false, className }) {
  const config = STATUS_MAP[status] ?? STATUS_MAP.neutral
  const variant = config.variant
  const displayLabel = label ?? config.label

  return (
    <span
      className={cn(
        'chip',
        VARIANT_CLASSES[variant],
        size === 'sm' && 'text-[0.6875rem] px-[0.45rem] py-[0.1rem]',
        className
      )}
    >
      {dot && (
        <span
          className={cn('inline-block w-[6px] h-[6px] rounded-full flex-shrink-0', DOT_CLASSES[variant])}
          aria-hidden="true"
        />
      )}
      {displayLabel}
    </span>
  )
}
