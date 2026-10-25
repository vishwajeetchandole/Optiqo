import { get } from './apiClient'
import { normalizeNetworkMap } from '@/lib/networkMap'

export async function getRunNetwork({ runId } = {}) {
  if (!runId) throw new Error('A planning run must be selected to load its network map.')
  const response = await get(`/runs/${encodeURIComponent(runId)}/network`)
  const network = normalizeNetworkMap(response)
  if (network.runId !== runId) {
    throw new Error('The backend returned a network for a different planning run.')
  }
  return network
}
