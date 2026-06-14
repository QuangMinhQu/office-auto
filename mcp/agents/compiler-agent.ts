import type { AgentTask, AgentResult } from "./base"
import { BaseAgent } from "./base"
import type { PipelineState } from "../state/pipeline-state"
import type { PipelineEvent } from "../state/events"
import { spawnPython, readJsonFile } from "../pipeline-core"

export class CompilerAgent extends BaseAgent {
  readonly agentId = "CompilerAgent"
  readonly phase = "compiling" as const

  async execute(task: AgentTask, state: PipelineState): Promise<AgentResult> {
    const events: PipelineEvent[] = []
    const runDir = task.run_dir

    const args = [
      "--run-dir", runDir,
      "--source-packet", `${runDir}/source_packet.json`,
    ]

    const styleMapPath = state.decisions.style_map?.path || `${runDir}/style_map.json`
    const replaceRangePath = state.decisions.replace_range?.path || `${runDir}/replace_range.json`

    args.push("--style-map", styleMapPath)
    args.push("--replace-range", replaceRangePath)

    const result = await spawnPython("source_packet_to_ops.py", args)

    if (result.exit_code !== 0) {
      return {
        ok: false,
        events,
        error: this.makeError(`Compilation failed: ${result.stderr}`, "COMPILE_FAILED"),
      }
    }

    const outputPath = `${runDir}/execution_ops.json`
    const execOps = await readJsonFile(outputPath).catch(() => ({}))
    const ops = execOps?.ops || []

    events.push({
      event_id: this.makeEventId(),
      run_id: task.run_id,
      type: "ArtifactCreated",
      phase: "compiled",
      agent: this.agentId,
      artifact: this.makeArtifactRef({
        name: "execution_ops",
        path: outputPath,
        schema: "execution_ops.v2",
      }),
      timestamp: this.now(),
      prev_revision: task.input_state_revision,
      next_revision: task.input_state_revision + 1,
    })

    return {
      ok: true,
      events,
      summary: `Compiled ${ops.length} ops (${ops.filter((o: any) => o.op !== "remove").length} insert, ${ops.filter((o: any) => o.op === "remove").length} remove)`,
    }
  }
}
