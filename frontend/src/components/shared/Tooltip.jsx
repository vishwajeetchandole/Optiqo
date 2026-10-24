import { useState, useRef, useEffect, useId } from 'react'
import { createPortal } from 'react-dom'
import { cn } from '@/lib/utils'

/**
 * Tooltip — lightweight, zero-dependency accessible tooltip primitive.
 * Uses React Portal to attach to document.body with fixed coordinates,
 * ensuring it is never clipped by parent overflow:hidden or overflow-y:auto containers.
 *
 * Props:
 *   content  – string or React node for tooltip body
 *   side     – 'top' | 'right' | 'bottom' | 'left' (default: 'right')
 *   delay    – delay in ms before showing (default: 150)
 *   disabled – if true, tooltip will not be displayed
 *   children – trigger element
 */
export function Tooltip({
  content,
  side = 'right',
  delay = 150,
  disabled = false,
  className,
  children,
}) {
  const [visible, setVisible] = useState(false)
  const [coords, setCoords] = useState(null)
  const timerRef = useRef(null)
  const triggerRef = useRef(null)
  const tooltipId = useId()

  const show = () => {
    if (disabled || !content) return
    clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => {
      if (triggerRef.current) {
        const rect = triggerRef.current.getBoundingClientRect()
        let top = 0
        let left = 0
        let transform = ''
        if (side === 'right') {
          top = rect.top + rect.height / 2
          left = rect.right + 10
          transform = 'translateY(-50%)'
        } else if (side === 'left') {
          top = rect.top + rect.height / 2
          left = rect.left - 10
          transform = 'translate(-100%, -50%)'
        } else if (side === 'top') {
          top = rect.top - 8
          left = rect.left + rect.width / 2
          transform = 'translate(-50%, -100%)'
        } else {
          top = rect.bottom + 8
          left = rect.left + rect.width / 2
          transform = 'translate(-50%, 0)'
        }
        setCoords({ top, left, transform })
      }
      setVisible(true)
    }, delay)
  }

  const hide = () => {
    clearTimeout(timerRef.current)
    setVisible(false)
  }

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && visible) {
        hide()
      }
    }
    const handleScrollOrResize = () => {
      if (visible) hide()
    }
    if (visible) {
      window.addEventListener('keydown', handleKeyDown)
      window.addEventListener('scroll', handleScrollOrResize, true)
      window.addEventListener('resize', handleScrollOrResize)
    }
    return () => {
      window.removeEventListener('keydown', handleKeyDown)
      window.removeEventListener('scroll', handleScrollOrResize, true)
      window.removeEventListener('resize', handleScrollOrResize)
      clearTimeout(timerRef.current)
    }
  }, [visible])

  if (!content || disabled) {
    return children
  }

  return (
    <div
      ref={triggerRef}
      className="relative inline-flex items-center"
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
      aria-describedby={visible ? tooltipId : undefined}
    >
      {children}
      {visible &&
        coords &&
        typeof document !== 'undefined' &&
        createPortal(
          <div
            id={tooltipId}
            role="tooltip"
            style={{
              position: 'fixed',
              top: `${coords.top}px`,
              left: `${coords.left}px`,
              transform: coords.transform,
            }}
            className={cn(
              'z-50 pointer-events-none px-2.5 py-1 text-xs font-medium tracking-tight rounded-md shadow-lg transition-opacity duration-150 whitespace-nowrap animate-fade-in',
              'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 border border-token/20',
              className
            )}
          >
            {content}
          </div>,
          document.body
        )}
    </div>
  )
}
