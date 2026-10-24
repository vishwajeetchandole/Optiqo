import { CheckCircle2, AlertCircle, XCircle } from 'lucide-react'
import { cn } from '@/lib/utils'

/**
 * StatusBanner — PRD 6.6 plan-status banner.
 *
 * variant:
 *   'ok'       – green  — "Valid plan ready"
 *   'warning'  – yellow — "Plan OK with warnings / fallback forecast used"
 *   'error'    – red    — "No valid plan — solver infeasible or timed out"
 *
 * Props:
 *   variant   – 'ok' | 'warning' | 'error'
 *   title     – override headline
 *   message   – detail text
 *   action    – optional React node (e.g. "Re-run solver" button)
 */

const CONFIG = {
  ok: {
    icon: CheckCircle2,
    bg: 'var(--color-success-bg)',
    border: 'var(--color-success-text)',
    text: 'var(--color-success-text)',
    defaultTitle: 'Valid plan ready',
  },
  warning: {
    icon: AlertCircle,
    bg: 'var(--color-warning-bg)',
    border: 'var(--color-warning-text)',
    text: 'var(--color-warning-text)',
    defaultTitle: 'Plan available with warnings',
  },
  error: {
    icon: XCircle,
    bg: 'var(--color-danger-bg)',
    border: 'var(--color-danger-text)',
    text: 'var(--color-danger-text)',
    defaultTitle: 'No valid plan available',
  },
}

export function StatusBanner({ variant = 'ok', title, message, action, className }) {
  const cfg = CONFIG[variant] ?? CONFIG.ok
  const Icon = cfg.icon

  return (
    <div
      className={cn('flex items-start gap-3 rounded-2xl border p-3.5', className)}
      style={{
        background: cfg.bg,
        borderColor: cfg.border,
        color: cfg.text,
      }}
      role="status"
      aria-live="polite"
    >
      <Icon className="w-5 h-5 flex-shrink-0 mt-0.5" strokeWidth={2} aria-hidden="true" />
      <div className="flex-1 min-w-0">
        <p className="font-semibold text-sm leading-snug">{title ?? cfg.defaultTitle}</p>
        {message && <p className="text-sm mt-0.5 opacity-80">{message}</p>}
      </div>
      {action && <div className="flex-shrink-0">{action}</div>}
    </div>
  )
}
