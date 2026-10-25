/**
 * Shared JSON API client for the FastAPI backend.
 */

const BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api'
).replace(/\/+$/, '')
const DEFAULT_TIMEOUT_MS = 30_000

export class ApiError extends Error {
  constructor(message, status = 0, code = 'UNKNOWN', detail = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.detail = detail
  }
}

function getErrorMessage(data, statusText) {
  const message = data?.message ?? data?.detail ?? data?.title ?? statusText
  if (typeof message === 'string') return message
  if (message != null) return JSON.stringify(message)
  return 'Request failed'
}

export async function request(path, options = {}) {
  const {
    method = 'GET',
    body,
    query,
    timeout = DEFAULT_TIMEOUT_MS,
    headers: extraHeaders = {},
  } = options

  const isFormData = typeof FormData !== 'undefined' && body instanceof FormData

  const url = new URL(`${BASE_URL}${path}`)
  if (query) {
    Object.entries(query).forEach(([key, value]) => {
      if (value != null) url.searchParams.set(key, String(value))
    })
  }

  const headers = {
    Accept: 'application/json',
    ...extraHeaders,
  }
  if (body != null && !isFormData) headers['Content-Type'] = 'application/json'

  let token = null
  try {
    token = typeof window !== 'undefined'
      ? window.localStorage.getItem('optiqo-token')
      : null
  } catch {
    // Storage may be unavailable in restricted browser contexts.
  }
  if (token) headers.Authorization = `Bearer ${token}`

  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeout)
  let response
  try {
    response = await fetch(url.toString(), {
      method,
      headers,
      body: body != null
        ? (isFormData ? body : JSON.stringify(body))
        : undefined,
      signal: controller.signal,
    })
  } catch (error) {
    if (controller.signal.aborted) {
      throw new ApiError('Request timed out', 408, 'TIMEOUT')
    }
    const reason = error instanceof Error ? error.message : 'Network error'
    throw new ApiError(
      `Unable to reach the Optiqo API at ${BASE_URL}. Make sure the backend is running and VITE_API_BASE_URL is correct. (${reason})`,
      0,
      'NETWORK_ERROR',
      error
    )
  } finally {
    clearTimeout(timeoutId)
  }

  let data = null
  if (response.status !== 204) {
    const contentType = response.headers.get('content-type') ?? ''
    if (contentType.includes('application/json') || contentType.includes('+json')) {
      try {
        data = await response.json()
      } catch (error) {
        throw new ApiError(
          'Backend returned an invalid JSON response',
          response.status,
          'INVALID_RESPONSE',
          error
        )
      }
    } else {
      data = await response.text()
    }
  }

  if (!response.ok) {
    throw new ApiError(
      getErrorMessage(data, response.statusText),
      response.status,
      data?.code ?? 'HTTP_ERROR',
      data
    )
  }

  return data
}

export const get = (path, options) => request(path, { ...options, method: 'GET' })
export const post = (path, options) => request(path, { ...options, method: 'POST' })
export const postForm = (path, formData, options = {}) => request(path, { ...options, method: 'POST', body: formData })
export const put = (path, options) => request(path, { ...options, method: 'PUT' })
export const del = (path, options) => request(path, { ...options, method: 'DELETE' })
