import type { PipelinePhase, ArtifactRef, CheckResult, PipelineError } from "./pipeline-state"

export type PipelineEventType =
  | "RunCreated"
  | "PhaseStarted"
  | "PhaseCompleted"
  | "PhaseFailed"
  | "ArtifactCreated"
  | "DecisionRecorded"
  | "AgentAssigned"
  | "AgentCompleted"
  | "AgentFailed"
  | "ValidationPassed"
  | "ValidationFailed"
  | "RetryScheduled"
  | "HumanReviewRequested"
  | "RunCompleted"
  | "RunFailed"

interface BaseEvent {
  event_id: string
  run_id: string
  type: PipelineEventType
  timestamp: string
  prev_revision: number
  next_revision: number
}

export interface RunCreated extends BaseEvent {
  type: "RunCreated"
  inputs: {
    template_file: string
    source_file: string
    target_file: string
    strict_mode: boolean
  }
}

export interface PhaseStarted extends BaseEvent {
  type: "PhaseStarted"
  phase: PipelinePhase
  agent?: string
}

export interface PhaseCompleted extends BaseEvent {
  type: "PhaseCompleted"
  phase: PipelinePhase
  agent?: string
  duration_ms?: number
}

export interface PhaseFailed extends BaseEvent {
  type: "PhaseFailed"
  phase: PipelinePhase
  agent?: string
  error: PipelineError
}

export interface ArtifactCreated extends BaseEvent {
  type: "ArtifactCreated"
  phase: PipelinePhase
  agent?: string
  artifact: ArtifactRef
}

export interface DecisionRecorded extends BaseEvent {
  type: "DecisionRecorded"
  phase: PipelinePhase
  decision_type: "style_map" | "replace_range" | "human_override"
  artifact: ArtifactRef
}

export interface AgentAssigned extends BaseEvent {
  type: "AgentAssigned"
  phase: PipelinePhase
  agent_id: string
  task_id: string
}

export interface AgentCompleted extends BaseEvent {
  type: "AgentCompleted"
  phase: PipelinePhase
  agent_id: string
  task_id: string
}

export interface AgentFailed extends BaseEvent {
  type: "AgentFailed"
  phase: PipelinePhase
  agent_id: string
  task_id: string
  error: PipelineError
}

export interface ValidationPassed extends BaseEvent {
  type: "ValidationPassed"
  phase: PipelinePhase
  check_type: string
  result: CheckResult
}

export interface ValidationFailed extends BaseEvent {
  type: "ValidationFailed"
  phase: PipelinePhase
  check_type: string
  result: CheckResult
}

export interface RetryScheduled extends BaseEvent {
  type: "RetryScheduled"
  phase: PipelinePhase
  agent_id?: string
  attempt: number
  max_attempts: number
}

export interface HumanReviewRequested extends BaseEvent {
  type: "HumanReviewRequested"
  phase: PipelinePhase
  reason: string
}

export interface RunCompleted extends BaseEvent {
  type: "RunCompleted"
  final_gate_passed: boolean
  target_file: string
}

export interface RunFailed extends BaseEvent {
  type: "RunFailed"
  failed_phase: PipelinePhase
  error: PipelineError
}

export type PipelineEvent =
  | RunCreated
  | PhaseStarted
  | PhaseCompleted
  | PhaseFailed
  | ArtifactCreated
  | DecisionRecorded
  | AgentAssigned
  | AgentCompleted
  | AgentFailed
  | ValidationPassed
  | ValidationFailed
  | RetryScheduled
  | HumanReviewRequested
  | RunCompleted
  | RunFailed

let _eventCounter = 0

export function generateEventId(): string {
  _eventCounter++
  const ts = Date.now().toString(36)
  const rand = Math.random().toString(36).slice(2, 6)
  return `evt_${ts}_${rand}_${_eventCounter}`
}
