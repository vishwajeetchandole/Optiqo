import { Link, useLocation } from 'react-router-dom'
import { ChevronRight, Home } from 'lucide-react'
import { cn } from '@/lib/utils'

const ROUTE_LABELS = {
  '/':           { section: 'Workspace',  name: 'Overview' },
  '/validation': { section: 'Workspace',  name: 'Data Validation' },
  '/risk':       { section: 'Analysis',   name: 'Risk Overview' },
  '/backtest':   { section: 'Analysis',   name: 'Backtesting' },
  '/plan':       { section: 'Operations', name: 'Distribution Plan' },
  '/runs':       { section: 'Operations', name: 'Run Details & Export' },
}

/**
 * Breadcrumbs — accessible breadcrumb navigation.
 * Automatically computes crumbs based on current location, or accepts custom items array.
 *
 * Props:
 *   items – optional override array: [{ label: string, to?: string }]
 */
export function Breadcrumbs({ items, className }) {
  const location = useLocation()

  let crumbs = items
  if (!crumbs) {
    const isLineDetail = location.pathname.startsWith('/plan/') && location.pathname !== '/plan'
    if (isLineDetail) {
      const lineId = location.pathname.replace('/plan/', '')
      crumbs = [
        { label: 'Operations', to: '/plan' },
        { label: 'Distribution Plan', to: '/plan' },
        { label: `Line ${lineId.replace(/^line-0*/, '') || lineId}` },
      ]
    } else {
      const meta = ROUTE_LABELS[location.pathname]
      if (meta) {
        if (location.pathname === '/') {
          crumbs = [{ label: 'Overview' }]
        } else {
          crumbs = [
            { label: meta.section, to: '/' },
            { label: meta.name },
          ]
        }
      } else {
        crumbs = [{ label: 'App' }]
      }
    }
  }

  return (
    <nav aria-label="Breadcrumb" className={cn('flex items-center text-xs text-muted', className)}>
      <ol className="flex items-center gap-1.5 list-none p-0 m-0">
        <li className="flex items-center">
          <Link
            to="/"
            className="hover:text-primary transition-colors flex items-center gap-1"
            aria-label="Home"
          >
            <Home className="w-3.5 h-3.5" aria-hidden="true" />
          </Link>
        </li>

        {crumbs.map((crumb, idx) => {
          const isLast = idx === crumbs.length - 1
          return (
            <li key={crumb.label + idx} className="flex items-center gap-1.5">
              <ChevronRight className="w-3 h-3 text-muted/50 flex-shrink-0" aria-hidden="true" />
              {crumb.to && !isLast ? (
                <Link
                  to={crumb.to}
                  className="hover:text-primary transition-colors font-medium text-muted truncate max-w-[140px]"
                >
                  {crumb.label}
                </Link>
              ) : (
                <span
                  className={cn(
                    'truncate max-w-[180px]',
                    isLast ? 'font-semibold text-ink' : 'text-muted'
                  )}
                  aria-current={isLast ? 'page' : undefined}
                >
                  {crumb.label}
                </span>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
