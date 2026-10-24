import { useEffect } from 'react'
import { X, Keyboard, ShieldCheck, Terminal } from 'lucide-react'

/**
 * HelpModal — accessible documentation and keyboard shortcut guide.
 *
 * Props:
 *   isOpen  – boolean
 *   onClose – () => void
 */
export function HelpModal({ isOpen, onClose }) {
  useEffect(() => {
    if (!isOpen) return
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  if (!isOpen) return null

  const SHORTCUTS = [
    { key: 'Ctrl + K', desc: 'Open Command Palette & Global Search' },
    { key: '?', desc: 'Open this Help & Keyboard Shortcuts dialog' },
    { key: 'Esc', desc: 'Close open dialogs, drawers, or search' },
    { key: 'Tab', desc: 'Navigate through interactive controls' },
  ]

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-fade-in"
      role="dialog"
      aria-modal="true"
      aria-labelledby="help-modal-title"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg rounded-2xl bg-surface border border-token shadow-2xl p-6 space-y-5 text-ink animate-scale-in"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b border-token">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-[var(--color-primary-subtle)] flex items-center justify-center text-primary">
              <Keyboard className="w-4 h-4" aria-hidden="true" />
            </div>
            <div>
              <h2 id="help-modal-title" className="text-base font-semibold tracking-tight">
                Help & Keyboard Shortcuts
              </h2>
              <p className="text-xs text-muted">Optiqo Supply Chain Optimization Platform</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="icon-btn-circle w-7 h-7"
            aria-label="Close help modal"
          >
            <X className="w-4 h-4" aria-hidden="true" />
          </button>
        </div>

        {/* Shortcuts list */}
        <div className="space-y-2">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">
            Keyboard Shortcuts
          </h3>
          <div className="divide-y divide-token/40 rounded-xl border border-token bg-sidebar/50 px-3 py-1">
            {SHORTCUTS.map(({ key, desc }) => (
              <div key={key} className="flex items-center justify-between py-2 text-xs">
                <span className="text-ink">{desc}</span>
                <kbd className="px-2 py-0.5 text-[0.6875rem] font-mono font-semibold rounded bg-surface border border-token shadow-sm text-ink">
                  {key}
                </kbd>
              </div>
            ))}
          </div>
        </div>

        {/* Architecture & Documentation reference */}
        <div className="space-y-2">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">
            Platform Reference
          </h3>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="p-3 rounded-xl border border-token bg-sidebar/30 space-y-1">
              <div className="flex items-center gap-1.5 font-medium text-ink">
                <Terminal className="w-3.5 h-3.5 text-primary" aria-hidden="true" />
                <span>Solver Engine</span>
              </div>
              <p className="text-[0.6875rem] text-muted">
                Optiqo MIP Solver v2.4.1 (HiGHS Optimizer v1.7.0)
              </p>
            </div>

            <div className="p-3 rounded-xl border border-token bg-sidebar/30 space-y-1">
              <div className="flex items-center gap-1.5 font-medium text-ink">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" aria-hidden="true" />
                <span>Simulated Dataset</span>
              </div>
              <p className="text-[0.6875rem] text-muted">
                Demo Multi-Echelon Supply Chain v1 (340 SKUs, 8 DCs)
              </p>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between pt-2 border-t border-token text-[0.6875rem] text-muted">
          <span>Documentation available in repository</span>
          <button
            onClick={onClose}
            className="btn btn-secondary text-xs px-3 py-1.5"
          >
            Got it
          </button>
        </div>
      </div>
    </div>
  )
}
