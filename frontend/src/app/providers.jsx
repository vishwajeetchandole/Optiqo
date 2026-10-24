import { RouterProvider } from 'react-router-dom'
import { router } from './router'
import { ToastProvider } from '@/components/shared/Toast'
import { ErrorBoundary } from '@/components/shared/ErrorBoundary'

/**
 * Providers — wraps the app in all context providers:
 * ErrorBoundary, ToastProvider, RouterProvider.
 */
export function Providers() {
  return (
    <ErrorBoundary>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </ErrorBoundary>
  )
}
