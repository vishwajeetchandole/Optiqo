/**
 * Forecast service backed by the FastAPI forecasting contract.
 */
import { post } from './apiClient'
import { DEFAULT_ORIGIN_DATE, ensureDemoData } from './backendApi'
import * as mock from '../mocks/forecast.mock'

const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === 'true'

async function requestForecast({ originDate = DEFAULT_ORIGIN_DATE, horizon = 7 } = {}) {
  await ensureDemoData()
  return post('/forecast', {
    timeout: 180_000,
    body: { origin_date: originDate, horizon_days: horizon },
  })
}

export async function getForecastSummary() {
  if (USE_MOCKS) return mock.getForecastSummary()
  return requestForecast()
}

export async function getForecastSeries(params = {}) {
  if (USE_MOCKS) return mock.getForecastSeries(params)
  const horizon = Math.min(28, Math.max(1, Number(params.horizon) || 7))
  const forecast = await requestForecast({
    originDate: params.originDate ?? DEFAULT_ORIGIN_DATE,
    horizon,
  })
  const rows = forecast.forecasts.filter(
    (item) => !params.sku || item.sku_id === params.sku
  )
  const series = Array.from({ length: horizon }, (_, index) => {
    const values = rows.flatMap((item) => {
      const demand = item.daily_forecast[index] ?? 0
      return [{
        forecast: demand,
        lowerBound: demand * item.scenario_multipliers.low,
        upperBound: demand * item.scenario_multipliers.high,
      }]
    })
    return {
      week: `Day ${index + 1}`,
      date: forecastDate(forecast.origin_date, index + 1),
      actual: null,
      forecast: values.reduce((sum, item) => sum + item.forecast, 0),
      lowerBound: values.reduce((sum, item) => sum + item.lowerBound, 0),
      upperBound: values.reduce((sum, item) => sum + item.upperBound, 0),
    }
  })

  return {
    source: 'api',
    sku: params.sku ?? 'Network total',
    series,
    forecastSummary: forecast.forecast_summary,
  }
}

function forecastDate(originDate, days) {
  const date = new Date(`${originDate}T00:00:00Z`)
  date.setUTCDate(date.getUTCDate() + days)
  return date.toISOString().slice(0, 10)
}
