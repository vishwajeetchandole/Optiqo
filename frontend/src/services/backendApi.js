import { get } from './apiClient'

export const DEFAULT_ORIGIN_DATE = '2024-11-16'

const demoDataRequests = new Map()

export function ensureDemoData(seed = 42) {
  if (!demoDataRequests.has(seed)) {
    const request = get('/demo-data', { query: { seed } }).catch((error) => {
      demoDataRequests.delete(seed)
      throw error
    })
    demoDataRequests.set(seed, request)
  }
  return demoDataRequests.get(seed)
}

export function addDays(isoDate, days) {
  const date = new Date(`${isoDate}T00:00:00Z`)
  date.setUTCDate(date.getUTCDate() + days)
  return date.toISOString().slice(0, 10)
}
