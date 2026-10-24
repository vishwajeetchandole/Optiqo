import { sleep } from '../lib/utils'

/** @returns {Promise<ForecastSummary>} */
export async function getForecastSummary() {
  await sleep(350)
  return {
    source: 'mock',
    runId: 'fcast-001',
    timestamp: '2024-11-15T08:00:00Z',
    method: 'FALLBACK_FORECAST',   // one of the PRD status codes
    horizon: 12,                   // weeks
    granularity: 'weekly',
    skuCount: 340,
    warehouseCount: 8,
  }
}

/** @returns {Promise<ForecastSeries>} */
export async function getForecastSeries({ horizon = 12 } = {}) {
  await sleep(400)
  const weeks = Array.from({ length: horizon }, (_, i) => ({
    week: `W${String(i + 1).padStart(2, '0')}`,
    actual: i < 4 ? Math.round(1800 + Math.random() * 400) : null,
    forecast: Math.round(1900 + Math.random() * 300),
    lowerBound: Math.round(1600 + Math.random() * 200),
    upperBound: Math.round(2200 + Math.random() * 200),
  }))
  return { source: 'mock', series: weeks }
}
