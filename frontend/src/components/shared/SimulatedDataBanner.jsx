import { FlaskConical } from 'lucide-react'

/**
 * SimulatedDataBanner — PRD N9.
 * Persistent banner labelling the dataset as simulated.
 * Shown at the top of every page when data is from simulation.
 *
 * Props:
 *   show  – boolean (default false — only render if true)
 */
export function SimulatedDataBanner({ show = true }) {
  if (!show) return null
  return (
    <div className="simulated-banner" role="status" aria-live="polite">
      <FlaskConical className="w-3.5 h-3.5 flex-shrink-0" strokeWidth={2} aria-hidden="true" />
      <span>Simulated data — results do not reflect real inventory positions</span>
    </div>
  )
}
