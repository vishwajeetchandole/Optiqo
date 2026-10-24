import { cn } from '@/lib/utils'

/**
 * PillTabs — pill-segmented tab control.
 *
 * Props:
 *   tabs      – [{ value, label }]
 *   value     – active tab value
 *   onChange  – (value) => void
 *   className
 */
export function PillTabs({ tabs = [], value, onChange, className }) {
  return (
    <div
      className={cn('pill-tabs-list', className)}
      role="tablist"
      aria-label="Tab navigation"
    >
      {tabs.map((tab) => {
        const isActive = tab.value === value
        return (
          <button
            key={tab.value}
            role="tab"
            aria-selected={isActive}
            data-state={isActive ? 'active' : 'inactive'}
            className="pill-tab"
            onClick={() => onChange?.(tab.value)}
            tabIndex={isActive ? 0 : -1}
          >
            {tab.label}
          </button>
        )
      })}
    </div>
  )
}
