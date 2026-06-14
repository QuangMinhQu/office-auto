import type { PipelinePhase } from "./pipeline-state"

type TransitionMap = Record<PipelinePhase, PipelinePhase[]>

export const allowedTransitions: TransitionMap = {
  created: ["inspecting"],
  inspecting: ["inspected", "failed"],
  inspected: ["source_parsing", "failed"],
  source_parsing: ["source_parsed", "failed"],
  source_parsed: ["mapping", "failed"],
  mapping: ["mapped", "paused", "failed"],
  mapped: ["compiling", "failed"],
  compiling: ["compiled", "failed"],
  compiled: ["validating", "failed"],
  validating: ["validated", "failed"],
  validated: ["applying", "failed"],
  applying: ["applied", "failed"],
  applied: ["verifying", "failed"],
  verifying: ["verified", "failed"],
  verified: ["qa", "failed"],
  qa: ["qa_passed", "failed"],
  qa_passed: ["reviewing", "failed"],
  reviewing: ["reviewed", "paused", "failed"],
  reviewed: ["refreshing", "failed"],
  refreshing: ["refreshed", "failed"],
  refreshed: ["final_gate", "failed"],
  final_gate: ["complete", "failed"],
  complete: [],
  failed: [],
  paused: [],
}

export function assertTransitionAllowed(from: PipelinePhase, to: PipelinePhase): void {
  const allowed = allowedTransitions[from]
  if (!allowed) {
    throw new Error(`Unknown phase: ${from}`)
  }
  if (!allowed.includes(to)) {
    throw new Error(`Invalid transition: ${from} → ${to}. Allowed: ${allowed.join(", ")}`)
  }
}

export function isTerminalPhase(phase: PipelinePhase): boolean {
  return phase === "complete" || phase === "failed"
}

export function isPausedPhase(phase: PipelinePhase): boolean {
  return phase === "paused"
}

export function getNextPhases(phase: PipelinePhase): PipelinePhase[] {
  return allowedTransitions[phase] || []
}

export function getPhaseAgent(phase: PipelinePhase): string {
  const agentMap: Record<PipelinePhase, string> = {
    created: "IntakeAgent",
    inspecting: "TemplateInspectorAgent",
    inspected: "TemplateInspectorAgent",
    source_parsing: "SourceParserAgent",
    source_parsed: "SourceParserAgent",
    mapping: "MapperAgent",
    mapped: "MapperAgent",
    compiling: "CompilerAgent",
    compiled: "CompilerAgent",
    validating: "ValidatorAgent",
    validated: "ValidatorAgent",
    applying: "ExecutorAgent",
    applied: "ExecutorAgent",
    verifying: "VerifierAgent",
    verified: "VerifierAgent",
    qa: "QAAgent",
    qa_passed: "QAAgent",
    reviewing: "ReviewerAgent",
    reviewed: "ReviewerAgent",
    refreshing: "PostProcessorAgent",
    refreshed: "PostProcessorAgent",
    final_gate: "FinalGateAgent",
    complete: "PipelineSupervisor",
    failed: "PipelineSupervisor",
    paused: "PipelineSupervisor",
  }
  return agentMap[phase] || "PipelineSupervisor"
}
