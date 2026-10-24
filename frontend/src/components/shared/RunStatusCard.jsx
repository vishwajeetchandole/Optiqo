import { Database, Activity } from 'lucide-react'
import { cn } from '@/lib/utils'
import { StatusChip } from './StatusChip'
import { Tooltip } from './Tooltip'

/**
 * RunStatusCard — compact dataset & engine status card for the pinned sidebar footer.
 * Displays dataset name, simulated badge, and latest solver run state.
 *
 * Props:
 *   collapsed – whether sidebar is collapsed into rail
 *   datasetName – defaults to 'demo-supply-chain-v1'
 *   runId – defaults to 'run-003'
 *   status – defaults to 'OK'
 */
export function RunStatusCard({
  collapsed = false,
  datasetName = 'demo-supply-chain-v1',
  runId = 'run-003',
  status = 'OK',
  className,
}) {
  if (collapsed) {
    return (
      <Tooltip content={`Dataset: ${datasetName} (Simulated) • Run: ${runId} (${status})`} side="right">
        <div
          className={cn(
            'w-10 h-10 rounded-xl flex items-center justify-center border border-token bg-surface/75 text-muted hover:text-primary transition-colors cursor-default',
            className
          )}
          aria-label={`Dataset status: ${status}`}
        >
          <Activity className="w-4 h-4 text-emerald-500" aria-hidden="true" />
        </div>
      </Tooltip>
    )
  }

  return (
    <div
      className={cn(
        'rounded-xl border border-token/80 bg-surface/90 p-2.5 shadow-sm space-y-1.5 transition-all',
        className
      )}
    >
      <div className="flex items-center justify-between gap-1 text-[0.6875rem]">
        <div className="flex items-center gap-1.5 font-medium text-muted truncate">
          <Database className="w-3.5 h-3.5 text-primary flex-shrink-0" aria-hidden="true" />
          <span className="truncate" title={datasetName}>
            Simulated v1
          </span>
        </div>
        <StatusChip status={status} size="sm" dot />
      </div>

      <div className="flex items-center justify-between text-[0.625rem] text-muted/80 pt-0.5 border-t border-token/40 tabular-nums">
        <span className="truncate">{runId}</span>
        <span className="font-medium text-primary/90">12w Horizon</span>
      </div>
    </div>
  )
}
