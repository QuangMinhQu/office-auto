import type { AgentTask, AgentResult } from "./base"
import { BaseAgent } from "./base"
import type { PipelineState } from "../state/pipeline-state"
import type { PipelineEvent } from "../state/events"
import { spawnPython } from "../pipeline-core"

export class SourceParserAgent extends BaseAgent {
  readonly agentId = "SourceParserAgent"
  readonly phase = "source_parsing" as const

  async execute(task: AgentTask, state: PipelineState): Promise<AgentResult> {
    const events: PipelineEvent[] = []

    const result = await spawnPython("source_packet.py", [
      "--source", state.inputs.source_file,
      "--run-dir", task.run_dir,
    ])

    if (result.exit_code !== 0) {
      return {
        ok: false,
        events,
        error: this.makeError(`Source parsing failed: ${result.stderr}`, "SOURCE_PARSE_FAILED"),
      }
    }

    const outputPath = `${task.run_dir}/source_packet.json`

    events.push({
      event_id: this.makeEventId(),
      run_id: task.run_id,
      type: "ArtifactCreated",
      phase: "source_parsed",
      agent: this.agentId,
      artifact: this.makeArtifactRef({
        name: "source_packet",
        path: outputPath,
        schema: "source_packet.v1",
      }),
      timestamp: this.now(),
      prev_revision: task.input_state_revision,
      next_revision: task.input_state_revision + 1,
    })

    return { ok: true, events, summary: "Source parsed" }
  }
}
