import { useState, useEffect } from 'react'
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  ShieldCheck,
  BarChart3,
  Truck,
  FlaskConical,
  FileDown,
  ChevronLeft,
  ChevronRight,
  Sun,
  Moon,
  HelpCircle,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useTheme } from '@/hooks/useTheme'
import { Tooltip } from './Tooltip'
import { RunStatusCard } from './RunStatusCard'
import { HelpModal } from './HelpModal'

const NAV_SECTIONS = [
  {
    title: 'Workspace',
    items: [
      { to: '/',           icon: LayoutDashboard, label: 'Overview' },
      { to: '/validation', icon: ShieldCheck,     label: 'Data Validation', badge: '3', badgeVariant: 'warning' },
    ],
  },
  {
    title: 'Analysis',
    items: [
      { to: '/risk',       icon: BarChart3,       label: 'Risk Overview',   badge: '3', badgeVariant: 'danger' },
      { to: '/backtest',   icon: FlaskConical,    label: 'Backtesting' },
    ],
  },
  {
    title: 'Operations',
    items: [
      { to: '/plan',       icon: Truck,           label: 'Distribution Plan' },
      { to: '/runs',       icon: FileDown,        label: 'Run Details & Export' },
    ],
  },
]

/**
 * Sidebar — modern FinSet navigation rail & full drawer.
 * Features:
 * - 3 grouped sections with uppercase muted headers
 * - Collapsible state persisted to localStorage
 * - Tooltips on icon rail when collapsed
 * - Alert badges with active state awareness
 * - Pinned footer: RunStatusCard, Help modal trigger, theme toggle
 *
 * Props:
 *   collapsed        – controlled collapse state (boolean)
 *   onToggleCollapse – () => void
 */
export function Sidebar({ collapsed = false, onToggleCollapse, isMobile = false }) {
  const { theme, toggle: toggleTheme } = useTheme()
  const [helpOpen, setHelpOpen] = useState(false)

  // Global '?' shortcut opens HelpModal
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Don't trigger if user is typing in an input or textarea
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable) {
        return
      }
      if (e.key === '?') {
        e.preventDefault()
        setHelpOpen(true)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  return (
    <>
      <aside
        className={cn(
          'relative flex flex-col h-full bg-sidebar border-r border-token transition-[width] duration-300 ease-in-out flex-shrink-0 select-none',
          collapsed ? 'w-16' : 'w-[220px]'
        )}
        aria-label="Main navigation"
      >
        {/* ── Logo ─────────────────────────────────────────────────── */}
        <div
          className={cn(
            'flex items-center gap-2.5 px-4 py-4 flex-shrink-0 border-b border-token/40',
            collapsed && 'justify-center px-0'
          )}
        >
          <div
            className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 shadow-sm"
            style={{ background: 'var(--color-primary)' }}
            aria-hidden="true"
          >
            <span className="text-white font-bold text-sm tracking-tight">O</span>
          </div>
          {!collapsed && (
            <div className="flex flex-col min-w-0">
              <span className="font-bold text-[1.05rem] text-ink tracking-tight whitespace-nowrap leading-tight">
                Optiqo
              </span>
              <span className="text-[0.625rem] text-muted uppercase tracking-wider font-semibold">
                Supply Chain MIP
              </span>
            </div>
          )}
        </div>

        {/* ── Collapse toggle button (desktop only) ────────────────── */}
        {!isMobile && onToggleCollapse && (
          <button
            id="sidebar-collapse-btn"
            data-testid="sidebar-collapse-btn"
            onClick={onToggleCollapse}
            className={cn(
              'absolute -right-3.5 top-[3.5rem] z-30 cursor-pointer',
              'w-7 h-7 rounded-full border border-token bg-surface shadow-card',
              'flex items-center justify-center',
              'text-muted hover:text-primary hover:border-primary transition-all active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary'
            )}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {collapsed
              ? <ChevronRight className="w-3.5 h-3.5" aria-hidden="true" />
              : <ChevronLeft  className="w-3.5 h-3.5" aria-hidden="true" />}
          </button>
        )}

        {/* ── Nav items (Categorized) ──────────────────────────────── */}
        <nav
          className="flex-1 px-2.5 py-3 space-y-4 overflow-y-auto overflow-x-hidden styled-scrollbar"
          aria-label="Application sections"
        >
          {NAV_SECTIONS.map((section) => (
            <div key={section.title} className="space-y-1">
              {!collapsed && (
                <div className="px-2.5 py-1 text-[0.625rem] font-bold uppercase tracking-wider text-muted">
                  {section.title}
                </div>
              )}

              <div className="space-y-0.5">
                {section.items.map(({ to, icon: Icon, label, badge, badgeVariant }) => {
                  const navLinkContent = (
                    <NavLink
                      to={to}
                      end={to === '/'}
                      className={({ isActive }) =>
                        cn(
                          'nav-item group relative',
                          isActive && 'active',
                          collapsed && 'justify-center px-0 h-10 w-10 mx-auto'
                        )
                      }
                      aria-label={label}
                    >
                      {({ isActive }) => (
                        <>
                          <div className="relative flex items-center justify-center flex-shrink-0">
                            <Icon
                              className="w-[18px] h-[18px] flex-shrink-0 transition-transform group-hover:scale-110"
                              strokeWidth={1.75}
                              aria-hidden="true"
                            />
                            {/* Dot indicator on icon when collapsed */}
                            {collapsed && badge && (
                              <span
                                className={cn(
                                  'absolute -top-1 -right-1 w-2 h-2 rounded-full ring-2 ring-sidebar',
                                  badgeVariant === 'warning' ? 'bg-amber-500' : 'bg-red-500'
                                )}
                                aria-hidden="true"
                              />
                            )}
                          </div>

                          {!collapsed && (
                            <>
                              <span className="truncate flex-1">{label}</span>
                              {badge && (
                                <span
                                  className={cn(
                                    'ml-auto text-[0.625rem] font-bold px-1.5 py-0.5 rounded-full transition-colors tabular-nums',
                                    isActive
                                      ? 'bg-white/20 text-white'
                                      : badgeVariant === 'warning'
                                      ? 'bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300'
                                      : 'bg-rose-100 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300'
                                  )}
                                  title={`${badge} alerts`}
                                >
                                  {badge}
                                </span>
                              )}
                            </>
                          )}
                        </>
                      )}
                    </NavLink>
                  )

                  if (collapsed) {
                    const tooltipText = badge ? `${label} (${badge} alerts)` : label
                    return (
                      <Tooltip key={to} content={tooltipText} side="right">
                        {navLinkContent}
                      </Tooltip>
                    )
                  }

                  return <div key={to}>{navLinkContent}</div>
                })}
              </div>
            </div>
          ))}
        </nav>

        {/* ── Bottom pinned footer ─────────────────────────────────── */}
        <div
          className={cn(
            'flex flex-col gap-2 p-2.5 border-t border-token/40 flex-shrink-0 bg-sidebar/50',
            collapsed && 'items-center px-1'
          )}
        >
          {/* Dataset & Solver Run Status Card */}
          <RunStatusCard collapsed={collapsed} />

          {/* Help trigger & Theme toggle pill row */}
          <div
            className={cn(
              'flex items-center gap-1.5 pt-1',
              collapsed ? 'flex-col items-center' : 'justify-between px-1'
            )}
          >
            {/* Help Button */}
            {collapsed ? (
              <Tooltip content="Help & Keyboard Shortcuts (?)" side="right">
                <button
                  onClick={() => setHelpOpen(true)}
                  className="icon-btn-circle w-8 h-8 text-muted hover:text-primary transition-colors"
                  aria-label="Help and shortcuts"
                >
                  <HelpCircle className="w-4 h-4" aria-hidden="true" />
                </button>
              </Tooltip>
            ) : (
              <button
                id="sidebar-help-btn"
                onClick={() => setHelpOpen(true)}
                className="flex items-center gap-1.5 text-xs font-medium text-muted hover:text-primary transition-colors py-1 px-1.5 rounded-lg hover:bg-token/20"
                aria-label="Open Help & Shortcuts"
              >
                <HelpCircle className="w-3.5 h-3.5 text-muted" aria-hidden="true" />
                <span>Help & Keys</span>
                <kbd className="ml-1 px-1 py-0.2 text-[0.5625rem] font-mono rounded bg-surface border border-token/60 text-muted">
                  ?
                </kbd>
              </button>
            )}

            {/* Theme toggle pill */}
            <div className="theme-toggle-pill" role="group" aria-label="Theme toggle">
              <button
                onClick={() => theme !== 'light' && toggleTheme()}
                className={cn('theme-toggle-btn', theme === 'light' && 'active')}
                aria-label="Light mode"
                aria-pressed={theme === 'light'}
              >
                <Sun className="w-3.5 h-3.5" aria-hidden="true" />
              </button>
              <button
                onClick={() => theme !== 'dark' && toggleTheme()}
                className={cn('theme-toggle-btn', theme === 'dark' && 'active')}
                aria-label="Dark mode"
                aria-pressed={theme === 'dark'}
              >
                <Moon className="w-3.5 h-3.5" aria-hidden="true" />
              </button>
            </div>
          </div>
        </div>
      </aside>

      {/* Accessible Help & Keyboard Shortcuts Modal */}
      <HelpModal isOpen={helpOpen} onClose={() => setHelpOpen(false)} />
    </>
  )
}
