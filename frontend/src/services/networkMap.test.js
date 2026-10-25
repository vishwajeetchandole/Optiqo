import { afterEach, describe, expect, it, vi } from 'vitest'
import { get } from './apiClient'
import { getRunNetwork } from './networkMap'

vi.mock('./apiClient', () => ({ get: vi.fn() }))

afterEach(() => vi.clearAllMocks())

const networkResponse = (runId) => ({
  dataset_id: 'demo_seed_42',
  dataset_hash: 'abc123',
  run_id: runId,
  origin_date: '2024-11-16',
  locations: [],
  flows: [],
})

describe('run-specific network map service', () => {
  it('requests and returns data for the selected planning run', async () => {
    get.mockResolvedValue(networkResponse('run-selected'))

    await expect(getRunNetwork({ runId: 'run-selected' })).resolves.toMatchObject({
      runId: 'run-selected',
      datasetHash: 'abc123',
      locations: [],
      flows: [],
    })
    expect(get).toHaveBeenCalledWith('/runs/run-selected/network')
  })

  it('rejects a network response associated with a different run', async () => {
    get.mockResolvedValue(networkResponse('run-stale'))

    await expect(getRunNetwork({ runId: 'run-current' })).rejects.toThrow(
      'The backend returned a network for a different planning run.'
    )
  })
})
