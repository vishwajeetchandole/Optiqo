import { Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-5 text-center px-4">
      <p
        className="text-[5rem] font-bold leading-none"
        style={{ color: 'var(--color-primary-lilac)' }}
        aria-hidden="true"
      >
        404
      </p>
      <h1 className="text-2xl font-bold text-ink">Page not found</h1>
      <p className="text-sm text-muted max-w-sm">
        The page you're looking for doesn't exist or has been moved.
      </p>
      <Link to="/" className="btn-pill btn-primary flex items-center gap-2 mt-2">
        <ArrowLeft className="w-4 h-4" aria-hidden="true" />
        Back to Overview
      </Link>
    </div>
  )
}
