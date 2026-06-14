import type { PipelinePhase, PipelineState, ArtifactRef, PipelineError } from "../state/pipeline-state"
import type { PipelineEvent } from "../state/events"
import { generateEventId } from "../state/events"

export interface AgentTask {
  run_id: string
  task_id: string
  phase: PipelinePhase
  run_dir: string
  input_state_revision: number
  required_artifacts: string[]
  output_artifacts: string[]
  idempotency_key: string
}

export interface AgentResult {
  ok: boolean
  events: PipelineEvent[]
  artifacts?: ArtifactRef[]
  error?: PipelineError
  summary?: string
}

export abstract class BaseAgent {
  abstract readonly agentId: string
  abstract readonly phase: PipelinePhase

  protected worktree: string

  constructor(worktree: string) {
    this.worktree = worktree
  }

  abstract execute(task: AgentTask, state: PipelineState): Promise<AgentResult>

  protected makeEventId(): string {
    return generateEventId()
  }

  protected now(): string {
    return new Date().toISOString()
  }

  protected makeError(message: string, code?: string, recoverable = false): PipelineError {
    return {
      phase: this.phase,
      agent: this.agentId,
      message,
      code,
      timestamp: this.now(),
      recoverable,
    }
  }

  protected makeArtifactRef(params: {
    name: string
    path: string
    schema?: string
  }): ArtifactRef {
    return {
      path: params.path,
      sha256: "",
      schema: params.schema,
      created_by: this.agentId,
      phase: this.phase,
      valid: true,
    }
  }
}
