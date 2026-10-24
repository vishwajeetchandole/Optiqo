import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Search,
  X,
  ArrowRight,
  ShieldCheck,
  BarChart3,
  Truck,
  FlaskConical,
  FileDown,
  LayoutDashboard,
  Database,
  Layers,
  Sparkles,
  Command,
} from 'lucide-react'
import { cn } from '@/lib/utils'

const COMMAND_ITEMS = [
  // Navigation
  { id: 'p-overview',   category: 'Navigation', title: 'Overview Dashboard', subtitle: 'Global metrics and pipeline stepper', path: '/', icon: LayoutDashboard },
  { id: 'p-validation', category: 'Navigation', title: 'Data Validation', subtitle: 'Input checks, schema anomalies, and invariants', path: '/validation', icon: ShieldCheck },
  { id: 'p-risk',       category: 'Navigation', title: 'Risk Overview', subtitle: 'Ranked SKU-destination pairs and shortages', path: '/risk', icon: BarChart3 },
  { id: 'p-plan',       category: 'Navigation', title: 'Distribution Plan', subtitle: 'Solver transfer recommendations and dispatch', path: '/plan', icon: Truck },
  { id: 'p-backtest',   category: 'Navigation', title: 'Backtesting', subtitle: 'Policy benchmarks (B1, B2, Optiqo) and K1-K8 KPIs', path: '/backtest', icon: FlaskConical },
  { id: 'p-runs',       category: 'Navigation', title: 'Run Details & Export', subtitle: 'Audit trail, solver manifest, and exports', path: '/runs', icon: FileDown },

  // SKUs
  { id: 'sku-1042', category: 'SKUs & Materials', title: 'SKU-1042', subtitle: 'Cold-Chain Vaccine Pack (Critical Stockout)', path: '/risk?sku=SKU-1042', icon: Database, badge: 'Critical', badgeVariant: 'danger' },
  { id: 'sku-2198', category: 'SKUs & Materials', title: 'SKU-2198', subtitle: 'Oncology Adjuvant Monoclonal (Expiry Risk)', path: '/risk?sku=SKU-2198', icon: Database, badge: 'High Risk', badgeVariant: 'warning' },
  { id: 'sku-3341', category: 'SKUs & Materials', title: 'SKU-3341', subtitle: 'Lyophilized Injectable Buffer (WH-2 Frankfurt)', path: '/plan?sku=SKU-3341', icon: Database },
  { id: 'sku-0887', category: 'SKUs & Materials', title: 'SKU-0887', subtitle: 'Pediatric Antibiotic Suspension (Dallas DC)', path: '/plan?sku=SKU-0887', icon: Database },

  // Network Nodes
  { id: 'node-wh3', category: 'Network Hubs', title: 'WH-3 (Chicago DC)', subtitle: 'Midwest Regional Distribution Hub', path: '/plan?destination=WH-3 (Chicago DC)', icon: Layers },
  { id: 'node-wh1', category: 'Network Hubs', title: 'WH-1 (Newark DC)', subtitle: 'Primary Atlantic Distribution Center', path: '/plan?destination=WH-1 (Newark DC)', icon: Layers },

  // Actions
  { id: 'act-val', category: 'Actions', title: 'Run Input Validation Scan', subtitle: 'Verify invariants on supply-chain dataset', path: '/validation', icon: Sparkles },
  { id: 'act-plan', category: 'Actions', title: 'Review Distribution Recommendations', subtitle: 'Analyze solver dispatch lines', path: '/plan', icon: Sparkles },
]

/**
 * CommandPalette — accessible dialog for global navigation, entity lookup, and quick actions.
 *
 * Props:
 *   isOpen  – boolean
 *   onClose – () => void
 */
export function CommandPalette({ isOpen, onClose }) {
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const inputRef = useRef(null)
  const navigate = useNavigate()

  // Reset query and focus on open
  useEffect(() => {
    if (isOpen) {
      setQuery('')
      setSelectedIndex(0)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [isOpen])

  // Filter items based on query
  const filteredItems = query.trim() === ''
    ? COMMAND_ITEMS
    : COMMAND_ITEMS.filter((item) =>
        item.title.toLowerCase().includes(query.toLowerCase()) ||
        item.subtitle.toLowerCase().includes(query.toLowerCase()) ||
        item.category.toLowerCase().includes(query.toLowerCase())
      )

  // Clamp selectedIndex when filtered results change
  useEffect(() => {
    setSelectedIndex(0)
  }, [query])

  const handleSelect = (item) => {
    onClose()
    if (item.path) {
      navigate(item.path)
    }
  }

  // Keyboard navigation inside palette
  const handleKeyDown = (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIndex((prev) => (prev + 1) % Math.max(1, filteredItems.length))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIndex((prev) => (prev - 1 + filteredItems.length) % Math.max(1, filteredItems.length))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (filteredItems[selectedIndex]) {
        handleSelect(filteredItems[selectedIndex])
      }
    } else if (e.key === 'Escape') {
      e.preventDefault()
      onClose()
    }
  }

  if (!isOpen) return null

  // Group filtered items by category
  const groups = filteredItems.reduce((acc, item) => {
    acc[item.category] = acc[item.category] || []
    acc[item.category].push(item)
    return acc
  }, {})

  let itemCounter = -1

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-20 px-4 bg-black/40 backdrop-blur-sm animate-fade-in"
      role="dialog"
      aria-modal="true"
      aria-label="Command palette and quick search"
      onClick={onClose}
    >
      <div
        className="w-full max-w-2xl rounded-2xl bg-surface border border-token shadow-2xl overflow-hidden animate-scale-in text-ink flex flex-col max-h-[75vh]"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handleKeyDown}
      >
        {/* Search Input Bar */}
        <div className="flex items-center gap-3 px-4 py-3.5 border-b border-token bg-surface">
          <Search className="w-5 h-5 text-muted flex-shrink-0" aria-hidden="true" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Type a page, SKU (e.g. SKU-1042), hub, or action..."
            className="w-full bg-transparent text-ink placeholder:text-muted/60 text-sm focus:outline-none"
            aria-autocomplete="list"
            aria-controls="command-palette-results"
          />
          {query && (
            <button
              onClick={() => setQuery('')}
              className="text-muted hover:text-ink transition-colors"
              aria-label="Clear search"
            >
              <X className="w-4 h-4" />
            </button>
          )}
          <kbd className="hidden sm:inline-flex items-center gap-0.5 px-2 py-0.5 text-[0.625rem] font-mono rounded bg-sidebar border border-token text-muted">
            <Command className="w-2.5 h-2.5" /> K
          </kbd>
        </div>

        {/* Results List */}
        <div
          id="command-palette-results"
          role="listbox"
          className="flex-1 overflow-y-auto styled-scrollbar p-2 space-y-3"
        >
          {filteredItems.length === 0 ? (
            <div className="py-12 text-center text-xs text-muted">
              No matching pages, SKUs, or actions found for &ldquo;{query}&rdquo;
            </div>
          ) : (
            Object.entries(groups).map(([category, items]) => (
              <div key={category} className="space-y-1">
                <div className="px-3 py-1 text-[0.625rem] font-bold uppercase tracking-wider text-muted">
                  {category}
                </div>
                {items.map((item) => {
                  itemCounter++
                  const currentIndex = itemCounter
                  const isSelected = selectedIndex === currentIndex
                  const Icon = item.icon

                  return (
                    <div
                      key={item.id}
                      role="option"
                      aria-selected={isSelected}
                      onClick={() => handleSelect(item)}
                      onMouseEnter={() => setSelectedIndex(currentIndex)}
                      className={cn(
                        'flex items-center justify-between px-3 py-2 rounded-xl text-xs cursor-pointer transition-colors',
                        isSelected
                          ? 'bg-[var(--color-primary-subtle)] text-primary'
                          : 'text-ink hover:bg-sidebar/80'
                      )}
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <div
                          className={cn(
                            'w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 transition-colors',
                            isSelected
                              ? 'bg-[var(--color-primary)] text-white'
                              : 'bg-sidebar text-muted border border-token/60'
                          )}
                        >
                          <Icon className="w-3.5 h-3.5" aria-hidden="true" />
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-semibold truncate">{item.title}</span>
                            {item.badge && (
                              <span
                                className={cn(
                                  'text-[0.625rem] font-bold px-1.5 py-0.2 rounded-full',
                                  item.badgeVariant === 'danger'
                                    ? 'bg-rose-100 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300'
                                    : 'bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300'
                                )}
                              >
                                {item.badge}
                              </span>
                            )}
                          </div>
                          <p className="text-[0.6875rem] text-muted truncate">{item.subtitle}</p>
                        </div>
                      </div>
                      <ArrowRight
                        className={cn(
                          'w-3.5 h-3.5 flex-shrink-0 transition-opacity',
                          isSelected ? 'opacity-100 text-primary' : 'opacity-0'
                        )}
                        aria-hidden="true"
                      />
                    </div>
                  )
                })}
              </div>
            ))
          )}
        </div>

        {/* Footer shortcuts helper */}
        <div className="flex items-center justify-between px-4 py-2 border-t border-token bg-sidebar/50 text-[0.6875rem] text-muted">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1">
              <kbd className="px-1.5 py-0.5 rounded bg-surface border border-token">↑↓</kbd> navigate
            </span>
            <span className="flex items-center gap-1">
              <kbd className="px-1.5 py-0.5 rounded bg-surface border border-token">↵</kbd> select
            </span>
            <span className="flex items-center gap-1">
              <kbd className="px-1.5 py-0.5 rounded bg-surface border border-token">esc</kbd> close
            </span>
          </div>
          <span className="text-[0.625rem]">Optiqo Quick Search</span>
        </div>
      </div>
    </div>
  )
}
