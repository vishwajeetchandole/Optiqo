import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, get, post } from './apiClient'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('API client', () => {
  it('serializes JSON requests and query parameters against the configured API base', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: { get: () => 'application/json' },
      json: async () => ({ accepted: true }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(post('/plan', {
      query: { run_id: 'run-123', ignored: undefined },
      body: { origin_date: '2024-11-16' },
    })).resolves.toEqual({ accepted: true })

    const [url, options] = fetchMock.mock.calls[0]
    expect(url).toBe('http://localhost:8000/api/plan?run_id=run-123')
    expect(options.method).toBe('POST')
    expect(options.headers['Content-Type']).toBe('application/json')
    expect(JSON.parse(options.body)).toEqual({ origin_date: '2024-11-16' })
  })

  it('surfaces RFC 7807 response details as structured API errors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      statusText: 'Unprocessable Entity',
      headers: { get: () => 'application/problem+json' },
      json: async () => ({
        code: 'INVALID_ORIGIN_DATE',
        title: 'Invalid planning date',
        detail: 'The date is outside available dataset history.',
      }),
    }))

    await expect(get('/risk')).rejects.toMatchObject({
      name: 'ApiError',
      message: 'The date is outside available dataset history.',
      status: 422,
      code: 'INVALID_ORIGIN_DATE',
    })
  })

  it('classifies network failures for callers to display', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))

    const request = get('/health')
    await expect(request).rejects.toBeInstanceOf(ApiError)
    await expect(request).rejects.toMatchObject({
      name: 'ApiError',
      message: expect.stringContaining('Make sure the backend is running'),
      status: 0,
      code: 'NETWORK_ERROR',
    })
  })
})
