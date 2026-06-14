import type { PipelineState, PipelinePhase } from "../state/pipeline-state"
import { getNextPhases, isTerminalPhase, isPausedPhase, getPhaseAgent } from "../state/transitions"

export interface RouteDecision {
  phase: PipelinePhase
  agent: string
  required_artifacts: string[]
  canProceed: boolean
}

export function route(state: PipelineState): RouteDecision | null {
  if (isTerminalPhase(state.phase)) return null
  if (isPausedPhase(state.phase)) return null

  const nextPhases = getNextPhases(state.phase)
  if (nextPhases.length === 0) return null

  // Prefer the first non-failed phase
  const next = nextPhases[0]
  if (next === "failed" || next === "paused") return null

  const agent = getPhaseAgent(next)
  const required = getRequiredArtifacts(next)

  return {
    phase: next,
    agent,
    required_artifacts: required,
    canProceed: true,
  }
}

function getRequiredArtifacts(phase: PipelinePhase): string[] {
  const map: Record<string, string[]> = {
    inspecting: [],
    inspected: [],
    source_parsing: [],
    source_parsed: ["docx_inspect_output"],
    mapping: ["docx_inspect_output"],
    mapped: ["source_packet", "docx_inspect_output"],
    compiling: ["source_packet", "style_map", "replace_range"],
    compiled: [],
    validating: ["execution_ops"],
    validated: [],
    applying: ["execution_ops"],
    applied: [],
    verifying: ["execute_ops_report"],
    verified: [],
    qa: ["execute_ops_report"],
    qa_passed: [],
    reviewing: [],
    reviewed: [],
    refreshing: [],
    refreshed: [],
    final_gate: ["execute_ops_report", "qa_report", "review_report"],
    complete: [],
    failed: [],
    paused: [],
    created: [],
  }
  return map[phase] || []
}

export function shouldRetry(phase: PipelinePhase, errorCode?: string): boolean {
  const nonRecoverable = [
    "VALIDATION_FAILED",
    "FINAL_GATE_FAILED",
    "EXECUTE_PARTIAL",
  ]
  if (errorCode && nonRecoverable.includes(errorCode)) return false
  return true
}
