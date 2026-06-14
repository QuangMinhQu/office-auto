import type { AgentTask, AgentResult } from "./base"
import { BaseAgent } from "./base"
import type { PipelineState } from "../state/pipeline-state"
import type { PipelineEvent } from "../state/events"
import { spawnPython } from "../pipeline-core"

export class PostProcessorAgent extends BaseAgent {
  readonly agentId = "PostProcessorAgent"
  readonly phase = "refreshing" as const

  async execute(task: AgentTask, state: PipelineState): Promise<AgentResult> {
    const events: PipelineEvent[] = []

    const result = await spawnPython("docx_refresh_fields.py", [
      "--target-file", state.inputs.target_file,
      "--strategy", "auto",
      "--run-dir", task.run_dir,
    ])

    events.push({
      event_id: this.makeEventId(),
      run_id: task.run_id,
      type: result.exit_code === 0 ? "PhaseCompleted" : "PhaseFailed",
      phase: "refreshed",
      agent: this.agentId,
      timestamp: this.now(),
      prev_revision: task.input_state_revision,
      next_revision: task.input_state_revision + 1,
      ...(result.exit_code !== 0 ? {
        error: this.makeError("Field refresh failed", "REFRESH_FAILED"),
      } : {}),
    } as PipelineEvent)

    return { ok: result.exit_code === 0, events, summary: "Fields refreshed" }
  }
}
