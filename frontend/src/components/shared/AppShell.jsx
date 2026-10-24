import { useState, useEffect, useRef } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { Menu } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'
import { SimulatedDataBanner } from './SimulatedDataBanner'
import { useScrollRestoration } from '@/hooks/useScrollRestoration'

/** Map routes to page metadata for the Topbar */
const PAGE_META = {
  '/':           { title: 'Overview',               subtitle: 'Inventory health at a glance' },
  '/validation': { title: 'Data Validation',         subtitle: 'Input quality checks and anomaly flags' },
  '/risk':       { title: 'Risk Overview',           subtitle: 'Stockout and overstock exposure' },
  '/plan':       { title: 'Distribution Plan',       subtitle: 'Solver-generated replenishment recommendations' },
  '/backtest':   { title: 'Backtesting',             subtitle: 'Historical strategy evaluation' },
  '/runs':       { title: 'Run Details & Export',    subtitle: 'Solver run history and data exports' },
}

const MOCK_USER = { name: 'Demo User', email: 'demo@optiqo.io' }

/**
 * AppShell — root layout: sidebar + main content area.
 * Enforces 3 strictly independent scrolling regions:
 * 1) Pinned Sidebar with internal nav scroll
 * 2) Sticky Navbar with dynamic scroll affordance shadow
 * 3) Main Content Container (sole page scroll container with scroll restoration)
 */
export function AppShell() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    try {
      return localStorage.getItem('optiqo_sidebar_collapsed') === 'true'
    } catch {
      return false
    }
  })
  const [mobileOpen, setMobileOpen] = useState(false)
  const location = useLocation()
  const overlayRef = useRef(null)

  const toggleSidebar = () => {
    setSidebarCollapsed((prev) => {
      const next = !prev
      try {
        localStorage.setItem('optiqo_sidebar_collapsed', String(next))
      } catch {
        // ignore storage errors
      }
      return next
    })
  }

  // Independent scroll restoration & scroll state on main container
  const { containerRef, isScrolled, lockScroll } = useScrollRestoration()

  const isLineDetail = location.pathname.startsWith('/plan/') && location.pathname !== '/plan'
  const meta = isLineDetail
    ? { title: 'Recommendation Detail', subtitle: 'Explainability & solver evidence' }
    : PAGE_META[location.pathname] ?? { title: 'Optiqo', subtitle: '' }

  // Close mobile drawer on route change
  useEffect(() => {
    setMobileOpen((open) => (open ? false : open))
  }, [location.pathname])

  // Lock only the main content scroll container when mobile drawer is open
  useEffect(() => {
    lockScroll(mobileOpen)
  }, [mobileOpen, lockScroll])

  return (
    <div className="app-shell-container">
      {/* ── Accessible Skip to Content Link ──────────────────────── */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-[var(--color-primary)] focus:text-white focus:rounded-full focus:shadow-xl focus:text-xs focus:font-semibold"
      >
        Skip to content
      </a>

      {/* ── Mobile overlay ────────────────────────────────────────── */}
      {mobileOpen && (
        <div
          ref={overlayRef}
          className="fixed inset-0 z-30 bg-black/40 backdrop-blur-sm lg:hidden"
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* ── Sidebar — desktop (always visible, pinned) ────────────── */}
      <div className="hidden lg:flex h-full flex-shrink-0">
        <Sidebar
          collapsed={sidebarCollapsed}
          onToggleCollapse={toggleSidebar}
        />
      </div>

      {/* ── Sidebar — mobile (drawer) ──────────────────────────────── */}
      <div
        className={cn(
          'fixed inset-y-0 left-0 z-40 h-full shadow-xl transition-transform duration-300 lg:hidden',
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        )}
        role="dialog"
        aria-modal="true"
        aria-label="Navigation"
      >
        <Sidebar collapsed={false} onToggleCollapse={() => setMobileOpen(false)} isMobile />
      </div>

      {/* ── Main viewport column ──────────────────────────────────── */}
      <div className="flex flex-col flex-1 min-w-0 h-full overflow-hidden">
        {/* Mobile topbar hamburger */}
        <div className="flex items-center gap-3 px-4 pt-4 lg:hidden">
          <button
            onClick={() => setMobileOpen(true)}
            className="icon-btn-circle w-9 h-9"
            aria-label="Open navigation"
            aria-expanded={mobileOpen}
          >
            <Menu className="w-4 h-4" aria-hidden="true" />
          </button>
        </div>

        {/* Sticky Navbar with dynamic scroll affordance */}
        <Topbar
          title={meta.title}
          subtitle={meta.subtitle}
          user={MOCK_USER}
          notifCount={2}
          isMock={import.meta.env.VITE_USE_MOCKS === 'true'}
          isScrolled={isScrolled}
        />

        {/* Sole scroll container for all page content */}
        <main
          ref={containerRef}
          id="main-content"
          className="flex-1 min-h-0 overflow-y-auto styled-scrollbar bg-[var(--color-page)] px-4 sm:px-6 pb-8 space-y-4"
          tabIndex={-1}
          aria-label="Page content"
        >
          {import.meta.env.VITE_USE_MOCKS === 'true' && (
            <div className="pt-1">
              <SimulatedDataBanner show />
            </div>
          )}
          <Outlet />
        </main>
      </div>
    </div>
  )
}
