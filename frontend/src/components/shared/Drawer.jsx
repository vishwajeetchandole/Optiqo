import { useEffect, useRef } from 'react'
import { X } from 'lucide-react'
import { cn } from '@/lib/utils'

/**
 * Slide-out Drawer component.
 *
 * Props:
 *   open        – boolean
 *   onClose     – () => void
 *   title       – string | ReactNode
 *   subtitle    – string | ReactNode
 *   children    – ReactNode
 *   width       – string (default 'max-w-lg')
 *   className   – string
 */
export function Drawer({
  open,
  onClose,
  title,
  subtitle,
  children,
  width = 'max-w-lg',
  className,
}) {
  const panelRef = useRef(null)
  const previousFocusRef = useRef(null)

  useEffect(() => {
    if (open) {
      previousFocusRef.current = document.activeElement
      const mainEl = document.getElementById('main-content')
      if (mainEl) {
        mainEl.style.overflow = 'hidden'
      }

      // Focus first focusable element inside drawer
      const timer = setTimeout(() => {
        if (panelRef.current) {
          const focusable = panelRef.current.querySelectorAll(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
          )
          if (focusable.length > 0) {
            focusable[0].focus()
          }
        }
      }, 50)

      function handleKeyDown(e) {
        if (e.key === 'Escape') {
          onClose?.()
          return
        }

        // Trap focus inside drawer
        if (e.key === 'Tab' && panelRef.current) {
          const focusable = Array.from(
            panelRef.current.querySelectorAll(
              'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
            )
          ).filter((el) => !el.disabled && el.offsetParent !== null)

          if (focusable.length === 0) return

          const firstEl = focusable[0]
          const lastEl = focusable[focusable.length - 1]

          if (e.shiftKey && document.activeElement === firstEl) {
            e.preventDefault()
            lastEl.focus()
          } else if (!e.shiftKey && document.activeElement === lastEl) {
            e.preventDefault()
            firstEl.focus()
          }
        }
      }

      window.addEventListener('keydown', handleKeyDown)
      return () => {
        clearTimeout(timer)
        if (mainEl) {
          mainEl.style.overflow = ''
        }
        window.removeEventListener('keydown', handleKeyDown)
        if (previousFocusRef.current && typeof previousFocusRef.current.focus === 'function') {
          previousFocusRef.current.focus()
        }
      }
    }
  }, [open, onClose])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end"
      role="dialog"
      aria-modal="true"
      aria-labelledby="drawer-title"
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/40 backdrop-blur-[2px] drawer-overlay"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Slide-out panel */}
      <div
        ref={panelRef}
        data-state={open ? 'open' : 'closed'}
        className={cn(
          'relative z-10 flex flex-col h-full w-full bg-[var(--color-surface)] shadow-2xl border-l border-token overflow-y-auto overscroll-contain styled-scrollbar drawer-panel',
          width,
          className
        )}
      >
        {/* Header */}
        <div className="flex items-start justify-between p-6 border-b border-token bg-[var(--color-surface)] sticky top-0 z-10">
          <div>
            <h2 id="drawer-title" className="text-lg font-bold text-ink">
              {title}
            </h2>
            {subtitle && (
              <p className="text-xs text-muted mt-1">{subtitle}</p>
            )}
          </div>
          <button
            onClick={onClose}
            className="icon-btn-circle ml-4"
            aria-label="Close drawer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 p-6 space-y-6">
          {children}
        </div>
      </div>
    </div>
  )
}
