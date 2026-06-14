import type { AgentTask, AgentResult } from "./base"
import { BaseAgent } from "./base"
import type { PipelineState, CheckResult } from "../state/pipeline-state"
import type { PipelineEvent } from "../state/events"
import { spawnPython, readJsonFile } from "../pipeline-core"

export class VerifierAgent extends BaseAgent {
  readonly agentId = "VerifierAgent"
  readonly phase = "verifying" as const

  async execute(task: AgentTask, state: PipelineState): Promise<AgentResult> {
    const events: PipelineEvent[] = []
    const runDir = task.run_dir

    const result = await spawnPython("verify_docx_output.py", [
      "--run-dir", runDir,
      "--target-file", state.inputs.target_file,
    ])

    const coverageReport = await readJsonFile(`${runDir}/coverage_report.json`).catch(() => null)

    const checkResult: CheckResult = {
      passed: result.exit_code === 0 && (coverageReport?.passed !== false),
      details: coverageReport || {},
      errors: coverageReport?.errors || [],
      warnings: coverageReport?.warnings || [],
    }

    events.push({
      event_id: this.makeEventId(),
      run_id: task.run_id,
      type: "ArtifactCreated",
      phase: "verified",
      agent: this.agentId,
      artifact: this.makeArtifactRef({
        name: "coverage_report",
        path: `${runDir}/coverage_report.json`,
        schema: "coverage.v1",
      }),
      timestamp: this.now(),
      prev_revision: task.input_state_revision,
      next_revision: task.input_state_revision + 1,
    })

    events.push({
      event_id: this.makeEventId(),
      run_id: task.run_id,
      type: checkResult.passed ? "ValidationPassed" : "ValidationFailed",
      phase: "verified",
      check_type: "coverage",
      result: checkResult,
      timestamp: this.now(),
      prev_revision: task.input_state_revision + 1,
      next_revision: task.input_state_revision + 2,
    })

    return { ok: true, events, summary: "Verification complete" }
  }
}
