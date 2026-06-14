import type { AgentTask, AgentResult } from "./base"
import { BaseAgent } from "./base"
import type { PipelineState } from "../state/pipeline-state"
import type { PipelineEvent } from "../state/events"
import { spawnPython, mergeJsonFile, readJsonFile } from "../pipeline-core"

export class TemplateInspectorAgent extends BaseAgent {
  readonly agentId = "TemplateInspectorAgent"
  readonly phase = "inspecting" as const

  async execute(task: AgentTask, state: PipelineState): Promise<AgentResult> {
    const events: PipelineEvent[] = []
    const templateFile = state.inputs.template_file
    const runDir = task.run_dir

    const result = await spawnPython("docx_inspect.py", [
      "--template-file", templateFile,
      "--run-dir", runDir,
    ])

    if (result.exit_code !== 0) {
      return {
        ok: false,
        events,
        error: this.makeError(`Inspection failed: ${result.stderr}`, "INSPECT_FAILED"),
      }
    }

    const outputPath = `${runDir}/docx_inspect_output.json`

    events.push({
      event_id: this.makeEventId(),
      run_id: task.run_id,
      type: "ArtifactCreated",
      phase: "inspected",
      agent: this.agentId,
      artifact: this.makeArtifactRef({
        name: "docx_inspect_output",
        path: outputPath,
        schema: "docx_inspect.v1",
      }),
      timestamp: this.now(),
      prev_revision: task.input_state_revision,
      next_revision: task.input_state_revision + 1,
    })

    return { ok: true, events, summary: "Template inspected" }
  }
}
