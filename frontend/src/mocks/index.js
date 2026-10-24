/**
 * Mock resolver index
 * -------------------
 * Pages NEVER import mocks directly.
 * All routing happens in src/services/*.js via VITE_USE_MOCKS.
 *
 * This file exists only as a barrel / documentation entry point.
 */
export { getValidationReport, triggerValidation, getValidationHistory } from './validation.mock'
export { getForecastSummary, getForecastSeries } from './forecast.mock'
export { getRiskOverview, getRiskBreakdown } from './risk.mock'
export { getDistributionPlan, getPlanLine, triggerPlan } from './plan.mock'
export { getBacktestSummary, getBacktestHistory, triggerBacktest } from './backtest.mock'
export { getRuns, getRun, exportRun } from './runs.mock'
