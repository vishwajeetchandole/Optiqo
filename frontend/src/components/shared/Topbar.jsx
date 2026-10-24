import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Search,
  Bell,
  ShieldAlert,
  CheckCircle2,
  AlertTriangle,
  WifiOff,
  Activity,
  Command,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { Breadcrumbs } from './Breadcrumbs'
import { UserMenu } from './UserMenu'
import { CommandPalette } from './CommandPalette'
import { StatusChip } from './StatusChip'
import { Tooltip } from './Tooltip'

const INITIAL_NOTIFICATIONS = [
  {
    id: 'notif-1',
    title: 'Critical Stockout Alert',
    message: 'SKU-1042 in WH-3 (Chicago DC) projected stockout in 2.8 days.',
    type: 'danger',
    path: '/risk?sku=SKU-1042',
    time: '10m ago',
    read: false,
  },
  {
    id: 'notif-2',
    title: 'Data Validation Warnings',
    message: '3 advisory warnings detected in demand table during validation scan.',
    type: 'warning',
    path: '/validation',
    time: '45m ago',
    read: false,
  },
  {
    id: 'notif-3',
    title: 'Optimal Distribution Plan Ready',
    message: 'Solver run plan-003 completed in 4.2s (18/18 invariants passed).',
    type: 'success',
    path: '/plan',
    time: '2h ago',
    read: false,
  },
]

/**
 * Topbar — sticky top navbar with dynamic elevation, breadcrumbs, command palette trigger,
 * notification popover, live solver status chip, and user menu.
 *
 * Props:
 *   title      – page title
 *   subtitle   – optional page subtitle
 *   user       – user object { name, email }
 *   isMock     – boolean flag for mock dataset indicator
 *   isScrolled – boolean indicating whether main container is scrolled down
 */
export function Topbar({
  title = 'Overview',
  subtitle,
  user = { name: 'Demo User', email: 'demo@optiqo.io' },
  isMock = false,
  isScrolled = false,
}) {
  const navigate = useNavigate()

  // Command palette state
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false)

  // Notifications state
  const [notifOpen, setNotifOpen] = useState(false)
  const [notifications, setNotifications] = useState(INITIAL_NOTIFICATIONS)
  const notifRef = useRef(null)

  // Offline detection state
  const [isOffline, setIsOffline] = useState(!navigator.onLine)

  useEffect(() => {
    const handleOnline = () => setIsOffline(false)
    const handleOffline = () => setIsOffline(true)
    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)
    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [])

  // Global Ctrl+K / Cmd+K listener
  useEffect(() => {
    function handleKeyDown(e) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setCommandPaletteOpen((prev) => !prev)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  // Close notifications on outside click
  useEffect(() => {
    function handleClickOutside(e) {
      if (notifRef.current && !notifRef.current.contains(e.target)) {
        setNotifOpen(false)
      }
    }
    if (notifOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [notifOpen])

  const unreadCount = notifications.filter((n) => !n.read).length

  const markAllRead = () => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })))
  }

  return (
    <>
      {/* Offline Banner if disconnected */}
      {isOffline && (
        <div className="bg-red-600 text-white text-xs px-4 py-2 font-semibold flex items-center justify-center gap-2 z-40">
          <WifiOff className="w-4 h-4" />
          <span>Network connection offline. Operating with local cached data.</span>
        </div>
      )}

      {/* Sticky Topbar Header */}
      <header
        className={cn(
          'sticky top-0 z-30 flex items-center justify-between gap-4 px-6 py-3.5 transition-all duration-200 select-none',
          'bg-[var(--color-shell)]/85 backdrop-blur-md',
          isScrolled
            ? 'border-b border-token shadow-[var(--shadow-navbar)]'
            : 'border-b border-transparent'
        )}
      >
        {/* Left Side: Breadcrumbs + Title */}
        <div className="min-w-0 space-y-1">
          <Breadcrumbs />
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-xl font-bold text-ink tracking-tight leading-none">{title}</h1>
            {isMock && (
              <span className="mock-tag text-[0.6875rem] py-0.5" aria-label="Using mock data">
                <span aria-hidden="true">◆</span> Mock data
              </span>
            )}
            {subtitle && (
              <span className="hidden md:inline-block text-xs text-muted font-normal">
                — {subtitle}
              </span>
            )}
          </div>
        </div>

        {/* Right Side: Command Trigger, Solver Status Chip, Notifications, User Menu */}
        <div className="flex items-center gap-2.5 flex-shrink-0">
          {/* Command Palette Trigger Button */}
          <button
            onClick={() => setCommandPaletteOpen(true)}
            className="flex items-center gap-2 px-2.5 py-1.5 rounded-full border border-token/80 bg-surface/80 hover:bg-surface hover:border-token text-xs text-muted hover:text-ink shadow-sm transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            aria-label="Open command search (Ctrl+K)"
          >
            <Search className="w-3.5 h-3.5 text-muted" aria-hidden="true" />
            <span className="hidden sm:inline text-xs">Search...</span>
            <kbd className="hidden sm:inline-flex items-center gap-0.5 px-1.5 py-0.2 text-[0.625rem] font-mono rounded bg-sidebar border border-token text-muted">
              <Command className="w-2.5 h-2.5" /> K
            </kbd>
          </button>

          {/* Solver Status Chip */}
          <div className="hidden lg:flex items-center">
            <Tooltip content="MIP Solver Engine Status: HiGHS converged (18/18 invariants passed)" side="bottom">
              <div className="flex items-center gap-1.5 px-2 py-1 rounded-full border border-token bg-surface/60 text-xs">
                <Activity className="w-3.5 h-3.5 text-emerald-500" aria-hidden="true" />
                <span className="text-[0.6875rem] font-medium text-muted">Solver:</span>
                <StatusChip status="OK" size="sm" dot />
              </div>
            </Tooltip>
          </div>

          {/* Notification Center Popover */}
          <div className="relative" ref={notifRef}>
            <Tooltip content="Notifications & Alerts" side="bottom">
              <button
                onClick={() => setNotifOpen((prev) => !prev)}
                className="icon-btn-circle w-8 h-8 relative focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                aria-label={`Notifications${unreadCount > 0 ? `, ${unreadCount} unread` : ''}`}
                aria-expanded={notifOpen}
              >
                <Bell className="w-4 h-4 text-muted" aria-hidden="true" />
                {unreadCount > 0 && (
                  <span
                    className="absolute -top-0.5 -right-0.5 min-w-[15px] h-[15px] px-1 rounded-full flex items-center justify-center text-[0.5625rem] font-bold text-white bg-red-600 ring-2 ring-surface tabular-nums"
                    aria-hidden="true"
                  >
                    {unreadCount}
                  </span>
                )}
              </button>
            </Tooltip>

            {/* Notification Dropdown Panel */}
            {notifOpen && (
              <div
                role="region"
                aria-label="Notifications list"
                className="absolute right-0 top-full mt-2 w-80 sm:w-96 rounded-2xl bg-surface shadow-2xl border border-token p-3 z-50 animate-scale-in text-xs space-y-2"
              >
                <div className="flex items-center justify-between pb-2 border-b border-token">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-ink text-xs">Notifications</span>
                    {unreadCount > 0 && (
                      <span className="chip chip-danger text-[10px] tabular-nums">
                        {unreadCount} unread
                      </span>
                    )}
                  </div>
                  {unreadCount > 0 && (
                    <button
                      onClick={markAllRead}
                      className="text-[11px] text-primary hover:underline font-semibold"
                    >
                      Mark all read
                    </button>
                  )}
                </div>

                <div className="divide-y divide-token/60 max-h-72 overflow-y-auto styled-scrollbar">
                  {notifications.map((notif) => (
                    <div
                      key={notif.id}
                      onClick={() => {
                        setNotifications((prev) =>
                          prev.map((n) => (n.id === notif.id ? { ...n, read: true } : n))
                        )
                        setNotifOpen(false)
                        navigate(notif.path)
                      }}
                      className={cn(
                        'py-2.5 px-2 flex items-start gap-2.5 cursor-pointer rounded-xl transition-colors hover:bg-token/20',
                        !notif.read && 'bg-primary/5 font-medium'
                      )}
                    >
                      {notif.type === 'danger' && (
                        <ShieldAlert className="w-4 h-4 text-danger flex-shrink-0 mt-0.5" />
                      )}
                      {notif.type === 'warning' && (
                        <AlertTriangle className="w-4 h-4 text-warning flex-shrink-0 mt-0.5" />
                      )}
                      {notif.type === 'success' && (
                        <CheckCircle2 className="w-4 h-4 text-success flex-shrink-0 mt-0.5" />
                      )}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-1">
                          <p className="font-semibold text-ink leading-snug">{notif.title}</p>
                          <span className="text-[10px] text-muted flex-shrink-0">{notif.time}</span>
                        </div>
                        <p className="text-muted text-[11px] mt-0.5 line-clamp-2">{notif.message}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* User Menu Dropdown */}
          <UserMenu user={user} />
        </div>
      </header>

      {/* Global Accessible Command Palette (Ctrl+K) */}
      <CommandPalette
        isOpen={commandPaletteOpen}
        onClose={() => setCommandPaletteOpen(false)}
      />
    </>
  )
}
