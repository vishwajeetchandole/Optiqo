import { ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'

/**
 * PillSelect — pill-shaped filter dropdown.
 *
 * Props:
 *   options   – [{ value, label }]
 *   value     – current selected value
 *   onChange  – (value) => void
 *   placeholder – shown when value is null/undefined
 *   className
 */
export function PillSelect({ options = [], value, onChange, placeholder = 'Select…', className }) {

  return (
    <div className={cn('relative inline-block', className)}>
      <select
        value={value ?? ''}
        onChange={(e) => onChange?.(e.target.value || null)}
        className={cn(
          'forms-select appearance-none cursor-pointer',
          'btn-pill btn-ghost pr-8 pl-4 py-[0.375rem] text-sm font-medium',
          'bg-[var(--color-surface)] text-[var(--color-ink)]',
          'border border-[var(--color-border)]',
          'focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] focus:ring-offset-0',
          'transition-colors'
        )}
        aria-label={placeholder}
      >
        {!value && <option value="">{placeholder}</option>}
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
      {/* Custom chevron */}
      <ChevronDown
        className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted"
        aria-hidden="true"
      />
    </div>
  )
}
