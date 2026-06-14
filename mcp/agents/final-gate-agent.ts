import type { AgentTask, AgentResult } from "./base"
import { BaseAgent } from "./base"
import type { PipelineState, CheckResult } from "../state/pipeline-state"
import type { PipelineEvent } from "../state/events"
import { spawnPython, readJsonFile } from "../pipeline-core"

export class FinalGateAgent extends BaseAgent {
  readonly agentId = "FinalGateAgent"
  readonly phase = "final_gate" as const

  async execute(task: AgentTask, state: PipelineState): Promise<AgentResult> {
    const events: PipelineEvent[] = []
    const runDir = task.run_dir

    const result = await spawnPython("final_gate.py", ["--run-dir", runDir])

    const gateReport = await readJsonFile(`${runDir}/final_gate.json`).catch(() => ({}))
    const gatePassed = gateReport?.passed === true

    const checkResult: CheckResult = {
      passed: gatePassed,
      details: gateReport || {},
      errors: gateReport?.failed_checks || gateReport?.missing_artifacts || [],
    }

    events.push({
      event_id: this.makeEventId(),
      run_id: task.run_id,
      type: "ArtifactCreated",
      phase: "final_gate",
      agent: this.agentId,
      artifact: this.makeArtifactRef({
        name: "final_gate",
        path: `${runDir}/final_gate.json`,
        schema: "final_gate.v1",
      }),
      timestamp: this.now(),
      prev_revision: task.input_state_revision,
      next_revision: task.input_state_revision + 1,
    })

    events.push({
      event_id: this.makeEventId(),
      run_id: task.run_id,
      type: gatePassed ? "ValidationPassed" : "ValidationFailed",
      phase: "final_gate",
      check_type: "final_gate",
      result: checkResult,
      timestamp: this.now(),
      prev_revision: task.input_state_revision + 1,
      next_revision: task.input_state_revision + 2,
    })

    if (gatePassed) {
      events.push({
        event_id: this.makeEventId(),
        run_id: task.run_id,
        type: "RunCompleted",
        final_gate_passed: true,
        target_file: state.inputs.target_file,
        timestamp: this.now(),
        prev_revision: task.input_state_revision + 2,
        next_revision: task.input_state_revision + 3,
      })
    } else {
      events.push({
        event_id: this.makeEventId(),
        run_id: task.run_id,
        type: "RunFailed",
        failed_phase: "final_gate",
        error: this.makeError(
          `Final gate failed: ${(gateReport?.failed_checks || []).join(", ")}`,
          "FINAL_GATE_FAILED",
        ),
        timestamp: this.now(),
        prev_revision: task.input_state_revision + 2,
        next_revision: task.input_state_revision + 3,
      })
    }

    return {
      ok: gatePassed,
      events,
      summary: gatePassed ? "Final gate passed" : `Final gate failed: ${(gateReport?.failed_checks || []).join(", ")}`,
    }
  }
}
