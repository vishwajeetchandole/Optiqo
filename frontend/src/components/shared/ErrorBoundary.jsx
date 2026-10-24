import React from 'react'
import { AlertTriangle, RotateCcw, Home } from 'lucide-react'

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null, errorInfo: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error('Uncaught error caught by ErrorBoundary:', error, errorInfo)
    this.setState({ errorInfo })
  }

  handleReload = () => {
    window.location.reload()
  }

  handleHome = () => {
    window.location.href = '/'
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center p-6 bg-[var(--color-bg)]">
          <div className="card max-w-lg w-full p-8 text-center space-y-4 shadow-2xl border-token">
            <div className="w-12 h-12 rounded-full bg-red-100 dark:bg-red-950/60 text-red-600 dark:text-red-400 flex items-center justify-center mx-auto">
              <AlertTriangle className="w-6 h-6" />
            </div>
            <h1 className="text-xl font-bold text-ink">Application Error</h1>
            <p className="text-sm text-muted">
              An unexpected error occurred in the dashboard interface. Your current session data has not been lost.
            </p>
            {this.state.error && (
              <div className="p-3.5 rounded-xl bg-[var(--color-tint)] text-left font-mono text-[11px] text-ink overflow-x-auto max-h-36">
                {this.state.error.toString()}
              </div>
            )}
            <div className="pt-2 flex items-center justify-center gap-3">
              <button
                onClick={this.handleReload}
                className="pill-btn-primary text-xs px-4 py-2 flex items-center gap-1.5"
              >
                <RotateCcw className="w-3.5 h-3.5" /> Reload Application
              </button>
              <button
                onClick={this.handleHome}
                className="pill-btn-outline text-xs px-4 py-2 flex items-center gap-1.5"
              >
                <Home className="w-3.5 h-3.5" /> Return to Overview
              </button>
            </div>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
