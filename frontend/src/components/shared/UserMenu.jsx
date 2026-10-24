import { useState, useRef, useEffect } from 'react'
import {
  Check,

  Building,
  Key,
  LogOut,
  Sun,
  Moon,
  ChevronDown,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useTheme } from '@/hooks/useTheme'

/**
 * UserMenu — dropdown menu for current user profile, workspace switcher, and theme settings.
 *
 * Props:
 *   user – { name: string, email: string, role?: string }
 */
export function UserMenu({ user = { name: 'Demo User', email: 'demo@optiqo.io' } }) {
  const [isOpen, setIsOpen] = useState(false)
  const [activeWorkspace, setActiveWorkspace] = useState('demo-supply-chain-v1')
  const menuRef = useRef(null)
  const { theme, toggle: toggleTheme } = useTheme()

  const WORKSPACES = [
    { id: 'demo-supply-chain-v1', name: 'Global Supply Chain v1', type: 'Simulated' },
    { id: 'regional-dc-emea',      name: 'EMEA Regional Pharma',    type: 'Read-only' },
  ]

  // Close on Escape or click outside
  useEffect(() => {
    if (!isOpen) return
    const handleClickOutside = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setIsOpen(false)
      }
    }
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [isOpen])

  const initials = user.name
    ? user.name
        .split(' ')
        .map((n) => n[0])
        .join('')
        .slice(0, 2)
        .toUpperCase()
    : 'U'

  return (
    <div ref={menuRef} className="relative inline-block text-left">
      <button
        onClick={() => setIsOpen((prev) => !prev)}
        className={cn(
          'flex items-center gap-2 py-1 px-2 rounded-full border transition-all text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary',
          isOpen
            ? 'border-primary bg-[var(--color-primary-subtle)]'
            : 'border-token/80 bg-surface/80 hover:bg-surface hover:border-token shadow-sm'
        )}
        aria-haspopup="menu"
        aria-expanded={isOpen}
        aria-label="User profile and workspace menu"
      >
        <div
          className="w-6 h-6 rounded-full flex items-center justify-center font-bold text-[0.6875rem] text-white flex-shrink-0"
          style={{ background: 'var(--color-primary)' }}
          aria-hidden="true"
        >
          {initials}
        </div>
        <div className="hidden sm:flex flex-col text-left leading-tight pr-1">
          <span className="font-semibold text-ink truncate max-w-[100px]">{user.name}</span>
          <span className="text-[0.625rem] text-muted truncate max-w-[100px]">Planner</span>
        </div>
        <ChevronDown
          className={cn('w-3 h-3 text-muted transition-transform duration-200', isOpen && 'rotate-180')}
          aria-hidden="true"
        />
      </button>

      {isOpen && (
        <div
          role="menu"
          aria-orientation="vertical"
          className="absolute right-0 mt-2 w-64 rounded-2xl bg-surface border border-token shadow-xl p-2 z-50 text-ink animate-scale-in space-y-2"
        >
          {/* User info banner */}
          <div className="px-3 py-2 border-b border-token/60 bg-sidebar/40 rounded-xl space-y-0.5">
            <p className="text-xs font-semibold text-ink truncate">{user.name}</p>
            <p className="text-[0.6875rem] text-muted truncate">{user.email}</p>
          </div>

          {/* Workspaces list */}
          <div className="space-y-1">
            <div className="px-3 py-1 text-[0.625rem] font-bold uppercase tracking-wider text-muted">
              Active Workspace
            </div>
            {WORKSPACES.map((ws) => (
              <button
                key={ws.id}
                role="menuitem"
                onClick={() => {
                  setActiveWorkspace(ws.id)
                  setIsOpen(false)
                }}
                className={cn(
                  'w-full flex items-center justify-between px-3 py-1.5 rounded-lg text-xs transition-colors text-left',
                  activeWorkspace === ws.id
                    ? 'bg-[var(--color-primary-subtle)] text-primary font-semibold'
                    : 'text-muted hover:bg-token/20 hover:text-ink'
                )}
              >
                <div className="flex items-center gap-2 truncate">
                  <Building className="w-3.5 h-3.5 flex-shrink-0 text-muted" aria-hidden="true" />
                  <span className="truncate">{ws.name}</span>
                </div>
                {activeWorkspace === ws.id && (
                  <Check className="w-3.5 h-3.5 text-primary flex-shrink-0" aria-hidden="true" />
                )}
              </button>
            ))}
          </div>

          {/* Theme Switch & Preferences */}
          <div className="pt-1 border-t border-token/60 space-y-1">
            <button
              role="menuitem"
              onClick={toggleTheme}
              className="w-full flex items-center justify-between px-3 py-1.5 rounded-lg text-xs text-muted hover:bg-token/20 hover:text-ink transition-colors"
            >
              <div className="flex items-center gap-2">
                {theme === 'dark' ? (
                  <Moon className="w-3.5 h-3.5 text-primary" aria-hidden="true" />
                ) : (
                  <Sun className="w-3.5 h-3.5 text-amber-500" aria-hidden="true" />
                )}
                <span>Theme Mode</span>
              </div>
              <span className="text-[0.6875rem] font-medium capitalize text-muted">
                {theme}
              </span>
            </button>

            <button
              role="menuitem"
              onClick={() => setIsOpen(false)}
              className="w-full flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs text-muted hover:bg-token/20 hover:text-ink transition-colors"
            >
              <Key className="w-3.5 h-3.5" aria-hidden="true" />
              <span>API Credentials</span>
            </button>
          </div>

          {/* Sign out */}
          <div className="pt-1 border-t border-token/60">
            <button
              role="menuitem"
              onClick={() => setIsOpen(false)}
              className="w-full flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/40 transition-colors"
            >
              <LogOut className="w-3.5 h-3.5" aria-hidden="true" />
              <span>Sign Out</span>
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
