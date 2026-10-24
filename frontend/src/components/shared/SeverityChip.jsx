import { cn } from '@/lib/utils'

/**
 * SeverityChip — for data validation severity levels.
 * severity: 'critical' | 'high' | 'medium' | 'low' | 'info'
 */

const SEVERITY_MAP = {
  critical: { cls: 'chip-danger',   label: 'Critical' },
  high:     { cls: 'chip-danger',   label: 'High' },
  medium:   { cls: 'chip-warning',  label: 'Medium' },
  low:      { cls: 'chip-neutral',  label: 'Low' },
  info:     { cls: 'chip-primary',  label: 'Info' },
}

export function SeverityChip({ severity = 'info', label, className }) {
  const { cls, label: defaultLabel } = SEVERITY_MAP[severity] ?? SEVERITY_MAP.info
  return (
    <span className={cn('chip', cls, className)}>
      {label ?? defaultLabel}
    </span>
  )
}
