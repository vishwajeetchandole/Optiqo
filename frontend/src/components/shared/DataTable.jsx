import { useState, useCallback } from 'react'
import { ChevronUp, ChevronDown, ChevronLeft, ChevronRight, StretchHorizontal, AlignJustify } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Skeleton, TableSkeleton } from './Skeleton'
import { EmptyState } from './EmptyState'
import { ErrorState } from './ErrorState'

/**
 * DataTable — high-density FinSet data table.
 *
 * Features:
 *   - Density toggle (comfortable vs compact) persisted in localStorage
 *   - Sticky table header with clean border
 *   - Selected row highlight (selectedRowKey)
 *   - Tabular numerals for alignment
 *   - Fully accessible sorting, pagination, and keyboard row triggers
 *
 * Props:
 *   columns             – [{ key, header, sortable?, render?, width?, align? }]
 *   data                – array of row objects
 *   loading             – show skeleton
 *   error               – show error state
 *   onRetry             – retry callback
 *   onRowClick          – (row) => void
 *   rowKey              – function or string to get a unique key per row (default 'id')
 *   selectedRowKey      – id of currently selected/active row
 *   enableDensityToggle – show density switch (default true)
 *
 *   // Pagination
 *   total               – total record count (for server-side pagination)
 *   page                – current page (1-indexed)
 *   pageSize            – rows per page
 *   onPageChange        – (page) => void
 *
 *   emptyTitle          – EmptyState title override
 *   emptyMessage        – EmptyState message override
 *   footer              – optional tfoot content
 *   className           – container class override
 */
export function DataTable({
  columns = [],
  data = [],
  loading = false,
  error = null,
  onRetry,
  onRowClick,
  rowKey = 'id',
  selectedRowKey,
  enableDensityToggle = false,
  total,
  page = 1,
  pageSize = 10,
  // Controlled sorting props
  sortKey: controlledSortKey,
  sortDir: controlledSortDir,
  onSort,

  emptyTitle,
  emptyMessage,
  footer,
  className,
}) {
  const [internalSortKey, setInternalSortKey] = useState(null)
  const [internalSortDir, setInternalSortDir] = useState('asc') // 'asc' | 'desc'
  const [density, setDensity] = useState(() => {
    try {
      return localStorage.getItem('optiqo_datatable_density') || 'comfortable'
    } catch {
      return 'comfortable'
    }
  })

  const handleDensityChange = (newDensity) => {
    setDensity(newDensity)
    try {
      localStorage.setItem('optiqo_datatable_density', newDensity)
    } catch {
      // ignore storage errors
    }
  }

  const isControlled = controlledSortKey !== undefined
  const activeSortKey = isControlled ? controlledSortKey : internalSortKey
  const activeSortDir = isControlled ? (controlledSortDir ?? 'asc') : internalSortDir

  const handleSort = useCallback(
    (key) => {
      if (onSort) {
        onSort(key)
      } else {
        if (internalSortKey === key) {
          setInternalSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
        } else {
          setInternalSortKey(key)
          setInternalSortDir('asc')
        }
      }
    },
    [onSort, internalSortKey]
  )

  // If controlled, parent handles sorting. If uncontrolled, sort client-side.
  const displayData = isControlled || onSort
    ? data
    : [...data].sort((a, b) => {
        if (!activeSortKey) return 0
        const av = a[activeSortKey]
        const bv = b[activeSortKey]
        if (av == null) return 1
        if (bv == null) return -1
        const cmp = typeof av === 'string' ? av.localeCompare(bv) : av - bv
        return activeSortDir === 'asc' ? cmp : -cmp
      })

  const totalPages = total != null ? Math.ceil(total / pageSize) : Math.ceil(data.length / pageSize)
  const getKey = (row, i) =>
    typeof rowKey === 'function' ? rowKey(row) : (row[rowKey] ?? i)

  const isCompact = density === 'compact'

  // ── Loading ──────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className={cn('overflow-hidden rounded-2xl border border-token bg-surface', className)}>
        {/* fake header */}
        <div className="table-header-pill flex gap-4 px-4 py-2.5">
          {columns.map((col) => (
            <Skeleton key={col.key} className="h-3 flex-1" />
          ))}
        </div>
        <div className="p-4">
          <TableSkeleton rows={5} cols={columns.length} />
        </div>
      </div>
    )
  }

  // ── Error ────────────────────────────────────────────────────────
  if (error) {
    return (
      <div className={cn('overflow-hidden rounded-2xl border border-token bg-surface', className)}>
        <ErrorState error={error} onRetry={onRetry} />
      </div>
    )
  }

  // ── Empty ────────────────────────────────────────────────────────
  if (displayData.length === 0) {
    return (
      <div className={cn('overflow-hidden rounded-2xl border border-token bg-surface', className)}>
        <EmptyState title={emptyTitle} message={emptyMessage} />
      </div>
    )
  }

  return (
    <div className={cn('flex flex-col', className)}>
      {/* Optional Top Density Bar */}
      {enableDensityToggle && (
        <div className="flex items-center justify-end gap-1 mb-2 px-1 text-xs text-muted">
          <span className="text-[0.6875rem] font-medium mr-1">Density:</span>
          <button
            onClick={() => handleDensityChange('comfortable')}
            className={cn(
              'flex items-center gap-1 px-2 py-0.5 rounded-md border text-[0.6875rem] transition-colors',
              density === 'comfortable'
                ? 'bg-primary text-white border-primary font-semibold'
                : 'border-token/60 bg-surface hover:bg-token/20'
            )}
            aria-label="Comfortable table density"
          >
            <AlignJustify className="w-3 h-3" /> Comfortable
          </button>
          <button
            onClick={() => handleDensityChange('compact')}
            className={cn(
              'flex items-center gap-1 px-2 py-0.5 rounded-md border text-[0.6875rem] transition-colors',
              density === 'compact'
                ? 'bg-primary text-white border-primary font-semibold'
                : 'border-token/60 bg-surface hover:bg-token/20'
            )}
            aria-label="Compact table density"
          >
            <StretchHorizontal className="w-3 h-3" /> Compact
          </button>
        </div>
      )}

      {/* Table Scrollable Container */}
      <div className="overflow-x-auto overflow-y-auto max-h-[500px] rounded-2xl border border-token styled-scrollbar bg-surface relative">
        <table className={cn('w-full border-collapse', isCompact ? 'text-xs' : 'text-sm')}>
          {/* ── Sticky header ── */}
          <thead className="sticky top-0 z-10 bg-surface shadow-[0_1px_0_0_var(--color-border)]">
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key}
                  scope="col"
                  className={cn(
                    'table-header-pill font-bold transition-colors select-none',
                    isCompact ? 'px-3 py-2' : 'px-4 py-2.5',
                    col.sortable && 'cursor-pointer hover:bg-[var(--color-primary-lilac)] hover:text-white',
                    col.align === 'right' && 'text-right',
                    col.align === 'center' && 'text-center'
                  )}
                  style={{ width: col.width }}
                  onClick={col.sortable ? () => handleSort(col.key) : undefined}
                  aria-sort={
                    activeSortKey === col.key
                      ? activeSortDir === 'asc'
                        ? 'ascending'
                        : 'descending'
                      : undefined
                  }
                  tabIndex={col.sortable ? 0 : undefined}
                  onKeyDown={
                    col.sortable
                      ? (e) => {
                          if (e.key === 'Enter' || e.key === ' ') handleSort(col.key)
                        }
                      : undefined
                  }
                >
                  <span className="inline-flex items-center gap-1">
                    {col.header}
                    {col.sortable && (
                      <span className="inline-flex flex-col flex-shrink-0" aria-hidden="true">
                        <ChevronUp
                          className={cn('w-2.5 h-2.5 -mb-1', activeSortKey === col.key && activeSortDir === 'asc' ? 'opacity-100' : 'opacity-30')}
                        />
                        <ChevronDown
                          className={cn('w-2.5 h-2.5', activeSortKey === col.key && activeSortDir === 'desc' ? 'opacity-100' : 'opacity-30')}
                        />
                      </span>
                    )}
                  </span>
                </th>
              ))}
            </tr>
          </thead>

          {/* ── Body ── */}
          <tbody className="divide-y divide-token">
            {displayData.map((row, i) => {
              const currentKey = getKey(row, i)
              const isSelected = selectedRowKey != null && currentKey === selectedRowKey

              return (
                <tr
                  key={currentKey}
                  className={cn(
                    'transition-colors',
                    onRowClick && 'cursor-pointer',
                    isSelected
                      ? 'bg-[var(--color-primary-subtle)] font-medium'
                      : onRowClick
                      ? 'hover:bg-[var(--color-tint)]'
                      : i % 2 === 1
                      ? 'bg-sidebar/30'
                      : 'bg-surface'
                  )}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  tabIndex={onRowClick ? 0 : undefined}
                  onKeyDown={
                    onRowClick
                      ? (e) => {
                          if (e.key === 'Enter' || e.key === ' ') onRowClick(row)
                        }
                      : undefined
                  }
                  role={onRowClick ? 'button' : undefined}
                  aria-label={onRowClick ? `Row ${i + 1}` : undefined}
                  aria-selected={isSelected || undefined}
                >
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className={cn(
                        'text-ink tabular-nums',
                        isCompact ? 'px-3 py-1.5' : 'px-4 py-2.5',
                        col.align === 'right' && 'text-right',
                        col.align === 'center' && 'text-center'
                      )}
                    >
                      {col.render
                        ? col.render(row[col.key] !== undefined ? row[col.key] : row, row)
                        : (row[col.key] ?? '—')}
                    </td>
                  ))}
                </tr>
              )
            })}
          </tbody>
          {footer && (
            <tfoot className="border-t-2 border-token bg-surface font-semibold sticky bottom-0">
              {footer}
            </tfoot>
          )}
        </table>
      </div>

      {/* ── Pagination ── */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-3 px-1">
          <p className="text-xs text-muted tabular-nums">
            Page {page} of {totalPages}
            {total != null && ` · ${total.toLocaleString()} records`}
          </p>
          <div className="flex items-center gap-1">
            <button
              onClick={() => onPageChange?.(page - 1)}
              disabled={page <= 1}
              className="icon-btn-circle disabled:opacity-30 disabled:cursor-not-allowed"
              aria-label="Previous page"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => onPageChange?.(page + 1)}
              disabled={page >= totalPages}
              className="icon-btn-circle disabled:opacity-30 disabled:cursor-not-allowed"
              aria-label="Next page"
            >
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
