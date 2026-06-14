import type { PipelinePhase } from "../state/pipeline-state"

interface RetryConfig {
  max_attempts: number
  base_delay_ms: number
  max_delay_ms: number
}

const DEFAULTS: RetryConfig = {
  max_attempts: 3,
  base_delay_ms: 1000,
  max_delay_ms: 30000,
}

const PHASE_OVERRIDES: Partial<Record<PipelinePhase, Partial<RetryConfig>>> = {
  applying: { max_attempts: 2, max_delay_ms: 60000 },
  compiling: { max_attempts: 5, base_delay_ms: 500 },
}

export function getRetryConfig(phase: PipelinePhase): RetryConfig {
  const overrides = PHASE_OVERRIDES[phase] || {}
  return { ...DEFAULTS, ...overrides }
}

export function computeBackoff(attempt: number, config: RetryConfig): number {
  const delay = Math.min(
    config.base_delay_ms * Math.pow(2, attempt - 1),
    config.max_delay_ms,
  )
  return delay
}

export function canRetry(phase: PipelinePhase, attempt: number, errorCode?: string): boolean {
  const config = getRetryConfig(phase)
  if (attempt >= config.max_attempts) return false

  const fatalCodes = ["VALIDATION_FAILED", "FINAL_GATE_FAILED"]
  if (errorCode && fatalCodes.includes(errorCode)) return false

  return true
}
