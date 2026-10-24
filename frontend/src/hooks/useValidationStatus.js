import { useState, useEffect, useCallback, useRef } from 'react'
import * as validationService from '@/services/validation'

/**
 * Pure function to compute the validation flow state.
 * @param {object|null} report
 * @returns {'idle'|'valid'|'invalid'|'warnings-only'}
 */
export function computeValidationState(report) {
  if (!report) return 'idle'
  if (report.errorsCount > 0) return 'invalid'
  if (report.warningsCount > 0) return 'warnings-only'
  return 'valid'
}

/**
 * Determines whether plan generation is permitted based on validation report.
 * Critical errors block plan generation, warnings allow it.
 * @param {object|null} report
 * @returns {boolean}
 */
export function isPlanGenerationAllowed(report) {
  const state = computeValidationState(report)
  return state !== 'invalid' && (report?.errorsCount || 0) === 0
}

/**
 * Hook to manage data validation state, workflow execution, and findings.
 */
export function useValidationStatus() {
  const [status, setStatus] = useState('idle') // 'idle' | 'validating' | 'valid' | 'invalid' | 'warnings-only'
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [progress, setProgress] = useState(0)
  const [selectedDataset, setSelectedDataset] = useState('demo-supply-chain-v1')
  const [selectedFinding, setSelectedFinding] = useState(null)

  const intervalRef = useRef(null)
  const timeoutRef = useRef(null)

  // Clean up any timers on unmount
  useEffect(() => {
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
    }
  }, [])

  const fetchReport = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await validationService.getValidationReport()
      setData(res)
      setStatus(computeValidationState(res))
    } catch (err) {
      setError(err?.message || 'Failed to load validation report')
      setStatus('idle')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    let mounted = true
    async function init() {
      setLoading(true)
      setError(null)
      try {
        const res = await validationService.getValidationReport()
        if (mounted) {
          setData(res)
          setStatus(computeValidationState(res))
        }
      } catch (err) {
        if (mounted) {
          setError(err?.message || 'Failed to load validation report')
          setStatus('idle')
        }
      } finally {
        if (mounted) setLoading(false)
      }
    }
    init()
    return () => {
      mounted = false
    }
  }, [])

  const runValidation = useCallback(async () => {
    setStatus('validating')
    setProgress(15)
    setError(null)

    if (intervalRef.current) clearInterval(intervalRef.current)
    intervalRef.current = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 85) return prev
        return prev + 20
      })
    }, 250)

    try {
      await validationService.triggerValidation({ dataset: selectedDataset })
      const res = await validationService.getValidationReport()
      if (intervalRef.current) clearInterval(intervalRef.current)
      setProgress(100)

      if (timeoutRef.current) clearTimeout(timeoutRef.current)
      timeoutRef.current = setTimeout(() => {
        setData(res)
        setStatus(computeValidationState(res))
        setProgress(0)
      }, 300)
    } catch (err) {
      if (intervalRef.current) clearInterval(intervalRef.current)
      setError(err?.message || 'Validation failed')
      setStatus('idle')
      setProgress(0)
    }
  }, [selectedDataset])

  return {
    status,
    setStatus,
    data,
    loading,
    error,
    progress,
    selectedDataset,
    setSelectedDataset,
    selectedFinding,
    setSelectedFinding,
    runValidation,
    refetch: fetchReport,
  }
}
