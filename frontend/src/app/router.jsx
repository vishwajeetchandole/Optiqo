import { createBrowserRouter, useRouteError, Link } from 'react-router-dom'
import { AppShell } from '@/components/shared/AppShell'
import { AlertTriangle, RotateCcw, Home } from 'lucide-react'

// ── Application pages (lazy-loaded for code splitting) ────────────
import { lazy, Suspense } from 'react'
import { CardSkeleton } from '@/components/shared/Skeleton'

const Overview              = lazy(() => import('@/pages/Overview'))
const DataValidation        = lazy(() => import('@/pages/DataValidation'))
const RiskOverview          = lazy(() => import('@/pages/RiskOverview'))
const DistributionPlan      = lazy(() => import('@/pages/DistributionPlan'))
const RecommendationDetail  = lazy(() => import('@/pages/RecommendationDetail'))
const Backtesting           = lazy(() => import('@/pages/Backtesting'))
const RunDetails            = lazy(() => import('@/pages/RunDetails'))
const NotFound              = lazy(() => import('@/pages/NotFound'))

// Generic loading fallback while lazy chunks load
function PageLoading() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mt-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <CardSkeleton key={i} />
      ))}
    </div>
  )
}

function Lazy({ component: Component }) {
  return (
    <Suspense fallback={<PageLoading />}>
      <Component />
    </Suspense>
  )
}

function RouteErrorBoundary() {
  const error = useRouteError()
  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-[var(--color-surface)]">
      <div className="card max-w-lg w-full p-8 text-center space-y-4 shadow-2xl border-token bg-[var(--color-surface)]">
        <div className="w-12 h-12 rounded-full bg-red-100 dark:bg-red-950/60 text-red-600 dark:text-red-400 flex items-center justify-center mx-auto">
          <AlertTriangle className="w-6 h-6" />
        </div>
        <h1 className="text-xl font-bold text-ink">Application Error</h1>
        <p className="text-sm text-muted">
          An unexpected error occurred in the dashboard view. Your session and settings have been preserved.
        </p>
        {error && (
          <div className="p-3.5 rounded-xl bg-[var(--color-tint)] text-left font-mono text-[11px] text-ink overflow-x-auto max-h-36">
            {error?.message || String(error)}
          </div>
        )}
        <div className="pt-2 flex items-center justify-center gap-3">
          <button
            onClick={() => window.location.reload()}
            className="pill-btn-primary text-xs px-4 py-2 flex items-center gap-1.5"
          >
            <RotateCcw className="w-3.5 h-3.5" /> Reload Application
          </button>
          <Link
            to="/"
            className="pill-btn-outline text-xs px-4 py-2 flex items-center gap-1.5"
          >
            <Home className="w-3.5 h-3.5" /> Return to Overview
          </Link>
        </div>
      </div>
    </div>
  )
}

export const router = createBrowserRouter([
  {
    element: <AppShell />,
    errorElement: <RouteErrorBoundary />,
    children: [
      { index: true,         element: <Lazy component={Overview} /> },
      { path: 'validation',  element: <Lazy component={DataValidation} /> },
      { path: 'risk',        element: <Lazy component={RiskOverview} /> },
      {
        path: 'plan',
        children: [
          { index: true,        element: <Lazy component={DistributionPlan} /> },
          { path: ':lineId',    element: <Lazy component={RecommendationDetail} /> },
        ],
      },
      { path: 'backtest',    element: <Lazy component={Backtesting} /> },
      { path: 'runs',        element: <Lazy component={RunDetails} /> },
      { path: '*',           element: <Lazy component={NotFound} /> },
    ],
  },
])
