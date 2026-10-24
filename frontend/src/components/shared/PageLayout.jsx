import React from 'react'
import { cn } from '@/lib/utils'

/**
 * Reusable PageLayout component adhering to FinSet design specifications:
 * - 12-column responsive layout grid
 * - Consistent spacing tokens
 * - Optional sticky filter slot
 * - Optional summary cards row (max 4 per row)
 * - Optional in-page section navigation anchors
 */
export function PageLayout({
  title,
  subtitle,
  badge,
  actions,
  filterBar,
  summaryCards,
  sectionNav,
  children,
  className,
}) {
  return (
    <div className={cn('flex flex-col gap-6 max-w-7xl mx-auto pb-12 w-full', className)}>
      {/* ── Page Header (When page-level actions/subtitles are provided) ──── */}
      {(title || actions) && (
        <header className="flex flex-col md:flex-row md:items-center justify-between gap-4 pt-1 flex-shrink-0">
          <div>
            <div className="flex items-center gap-2.5 flex-wrap">
              {title && (
                <h1 className="text-xl md:text-2xl font-bold tracking-tight text-ink flex items-center gap-2">
                  {title}
                </h1>
              )}
              {badge}
            </div>
            {subtitle && (
              <p className="text-xs md:text-sm text-muted mt-0.5 leading-relaxed max-w-3xl">
                {subtitle}
              </p>
            )}
          </div>

          {actions && (
            <div className="flex items-center flex-wrap gap-2.5 flex-shrink-0">
              {actions}
            </div>
          )}
        </header>
      )}

      {/* ── In-page Section Navigation Bar (for long analytical reports) ─── */}
      {sectionNav && (
        <nav
          className="sticky top-0 z-20 -mt-2 py-2 px-1 bg-[var(--color-surface)]/90 backdrop-blur-md border-b border-token flex items-center gap-2 overflow-x-auto text-xs"
          aria-label="Section navigation"
        >
          {sectionNav}
        </nav>
      )}

      {/* ── Summary Stat Cards (Max 4 per row, responsive 12-col grid) ───── */}
      {summaryCards && (
        <section aria-label="Summary metrics" className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {summaryCards}
        </section>
      )}

      {/* ── Optional Sticky Filter Slot ─────────────────────────────────── */}
      {filterBar && (
        <div className="sticky top-0 z-20 py-2.5 px-4 rounded-2xl bg-[var(--color-surface)]/95 backdrop-blur-md border border-token shadow-sm">
          {filterBar}
        </div>
      )}

      {/* ── Main Content Area ───────────────────────────────────────────── */}
      <div className="space-y-6">
        {children}
      </div>
    </div>
  )
}
