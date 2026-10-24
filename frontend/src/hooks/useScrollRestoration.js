import { useEffect, useRef, useState, useCallback } from 'react'
import { useLocation, useNavigationType } from 'react-router-dom'

// Session cache for scroll positions across routes
const scrollPositions = new Map()

/**
 * useScrollRestoration
 * Handles scroll restoration, scroll locking for drawers/dialogs,
 * hash anchor navigation, and scroll affordance state (isScrolled)
 * strictly on the main content container (body never scrolls).
 */
export function useScrollRestoration() {
  const containerRef = useRef(null)
  const location = useLocation()
  const navigationType = useNavigationType()
  const [isScrolled, setIsScrolled] = useState(false)
  const savedScrollBeforeLock = useRef(0)

  // Track scroll position and scroll affordance
  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    function handleScroll() {
      const top = el.scrollTop
      setIsScrolled(top > 6)
      scrollPositions.set(location.pathname, top)
    }

    el.addEventListener('scroll', handleScroll, { passive: true })
    return () => el.removeEventListener('scroll', handleScroll)
  }, [location.pathname])

  // Route change scroll restoration / reset
  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    // Check for hash link navigation (e.g. #kpis, #decomposition)
    if (location.hash) {
      const targetId = location.hash.replace('#', '')
      const targetEl = document.getElementById(targetId)
      if (targetEl) {
        const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
        targetEl.scrollIntoView({ behavior: prefersReduced ? 'auto' : 'smooth' })
        return
      }
    }

    // Back / Forward browser navigation: restore saved position
    if (navigationType === 'POP' && scrollPositions.has(location.pathname)) {
      const savedTop = scrollPositions.get(location.pathname) || 0
      el.scrollTop = savedTop
      setIsScrolled(savedTop > 6)
    } else {
      // Forward push/replace: reset to top
      el.scrollTop = 0
      setIsScrolled(false)
    }
  }, [location.pathname, location.hash, navigationType])

  /**
   * Lock/unlock scrolling strictly on the main content container
   * without affecting the document body or sidebar.
   */
  const lockScroll = useCallback((locked) => {
    const el = containerRef.current
    if (!el) return

    if (locked) {
      savedScrollBeforeLock.current = el.scrollTop
      el.style.overflowY = 'hidden'
    } else {
      el.style.overflowY = 'auto'
      el.scrollTop = savedScrollBeforeLock.current
    }
  }, [])

  return { containerRef, isScrolled, lockScroll }
}
