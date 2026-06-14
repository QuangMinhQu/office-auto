import type { AgentTask, AgentResult } from "./base"
import { BaseAgent } from "./base"
import type { PipelineState, CheckResult } from "../state/pipeline-state"
import type { PipelineEvent } from "../state/events"
import { spawnPython, readJsonFile } from "../pipeline-core"

export class ValidatorAgent extends BaseAgent {
  readonly agentId = "ValidatorAgent"
  readonly phase = "validating" as const

  async execute(task: AgentTask, state: PipelineState): Promise<AgentResult> {
    const events: PipelineEvent[] = []
    const runDir = task.run_dir
    const opsFile = `${runDir}/execution_ops.json`

    const strictResult = await spawnPython("validate_ops_strict.py", [
      "--run-dir", runDir,
      "--ops-file", opsFile,
    ])

    const strictReport = await readJsonFile(`${runDir}/strict_validation.json`).catch(() => ({}))
    const valid = strictReport?.valid === true

    const checkResult: CheckResult = {
      passed: valid,
      details: {
        high_severity_count: strictReport?.high_severity_count || 0,
        warning_count: strictReport?.warning_count || 0,
      },
      errors: strictReport?.blocking_errors || [],
      warnings: strictReport?.warnings || [],
    }

    events.push({
      event_id: this.makeEventId(),
      run_id: task.run_id,
      type: valid ? "ValidationPassed" : "ValidationFailed",
      phase: "validated",
      check_type: "strict_validation",
      result: checkResult,
      timestamp: this.now(),
      prev_revision: task.input_state_revision,
      next_revision: task.input_state_revision + 1,
    })

    await spawnPython("docx_validate_ops.py", [
      "--run-dir", runDir,
      "--ops-file", opsFile,
    ])

    events.push({
      event_id: this.makeEventId(),
      run_id: task.run_id,
      type: "ArtifactCreated",
      phase: "validated",
      agent: this.agentId,
      artifact: this.makeArtifactRef({
        name: "strict_validation",
        path: `${runDir}/strict_validation.json`,
        schema: "validation.v1",
      }),
      timestamp: this.now(),
      prev_revision: task.input_state_revision + 1,
      next_revision: task.input_state_revision + 2,
    })

    events.push({
      event_id: this.makeEventId(),
      run_id: task.run_id,
      type: "ArtifactCreated",
      phase: "validated",
      agent: this.agentId,
      artifact: this.makeArtifactRef({
        name: "execution_ops_validation",
        path: `${runDir}/execution_ops_validation.json`,
        schema: "validation.v1",
      }),
      timestamp: this.now(),
      prev_revision: task.input_state_revision + 2,
      next_revision: task.input_state_revision + 3,
    })

    if (!valid && state.inputs.strict_mode) {
      return {
        ok: false,
        events,
        error: this.makeError(
          `Strict validation failed: ${(strictReport?.blocking_errors || []).join(", ")}`,
          "VALIDATION_FAILED",
        ),
      }
    }

    return { ok: true, events, summary: `Validation ${valid ? "passed" : "had warnings"}` }
  }
}
