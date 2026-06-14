export type PipelinePhase =
  | "created"
  | "inspecting"
  | "inspected"
  | "source_parsing"
  | "source_parsed"
  | "mapping"
  | "mapped"
  | "compiling"
  | "compiled"
  | "validating"
  | "validated"
  | "applying"
  | "applied"
  | "verifying"
  | "verified"
  | "qa"
  | "qa_passed"
  | "reviewing"
  | "reviewed"
  | "refreshing"
  | "refreshed"
  | "final_gate"
  | "complete"
  | "failed"
  | "paused"

export type RunStatus = "running" | "paused" | "failed" | "complete"

export interface ArtifactRef {
  path: string
  sha256: string
  schema?: string
  created_by?: string
  phase?: PipelinePhase
  valid: boolean
}

export interface CheckResult {
  passed: boolean
  details?: Record<string, unknown>
  errors?: string[]
  warnings?: string[]
}

export interface AgentRunState {
  agent_id: string
  status: "pending" | "running" | "completed" | "failed"
  started_at?: string
  completed_at?: string
  revision?: number
  error?: string
}

export interface PipelineError {
  phase: PipelinePhase
  agent?: string
  message: string
  code?: string
  timestamp: string
  recoverable: boolean
}

export interface PipelineState {
  run_id: string
  pipeline_version: string
  phase: PipelinePhase
  status: RunStatus

  inputs: {
    template_file: string
    source_file: string
    target_file: string
    strict_mode: boolean
  }

  artifacts: Record<string, ArtifactRef>

  agents: Record<string, AgentRunState>

  decisions: {
    style_map?: ArtifactRef
    replace_range?: ArtifactRef
    human_overrides?: ArtifactRef[]
  }

  checks: {
    strict_validation?: CheckResult
    execution?: CheckResult
    coverage?: CheckResult
    qa?: CheckResult
    review?: CheckResult
    final_gate?: CheckResult
  }

  errors: PipelineError[]

  revision: number
  created_at: string
  updated_at: string
}

export function createInitialState(params: {
  run_id: string
  template_file: string
  source_file: string
  target_file: string
  strict_mode?: boolean
}): PipelineState {
  const now = new Date().toISOString()
  return {
    run_id: params.run_id,
    pipeline_version: "3",
    phase: "created",
    status: "running",
    inputs: {
      template_file: params.template_file,
      source_file: params.source_file,
      target_file: params.target_file,
      strict_mode: params.strict_mode ?? true,
    },
    artifacts: {},
    agents: {},
    decisions: {},
    checks: {},
    errors: [],
    revision: 0,
    created_at: now,
    updated_at: now,
  }
}
