import type { AgentTask, AgentResult } from "./base"
import { BaseAgent } from "./base"
import type { PipelineState, CheckResult } from "../state/pipeline-state"
import type { PipelineEvent } from "../state/events"
import { spawnPython, readJsonFile } from "../pipeline-core"

export class ExecutorAgent extends BaseAgent {
  readonly agentId = "ExecutorAgent"
  readonly phase = "applying" as const

  async execute(task: AgentTask, state: PipelineState): Promise<AgentResult> {
    const events: PipelineEvent[] = []
    const runDir = task.run_dir
    const targetFile = state.inputs.target_file

    const result = await spawnPython("execute_execution_ops.py", [
      "--run-dir", runDir,
      "--template-file", state.inputs.template_file,
      "--target-file", targetFile,
    ], { timeout: 600_000 })

    const opsReport = await readJsonFile(`${runDir}/execute_ops_report.json`).catch(() => null)

    if (!opsReport) {
      return {
        ok: false,
        events,
        error: this.makeError("Executor crashed or timed out before writing execute_ops_report.json", "EXECUTE_CRASHED"),
      }
    }

    const buildStatus = opsReport?.failed === 0 ? "completed" : "partial"
    const checkResult: CheckResult = {
      passed: buildStatus === "completed",
      details: {
        ops_applied: opsReport?.succeeded || 0,
        ops_failed: opsReport?.failed || 0,
        build_status: buildStatus,
      },
    }

    events.push({
      event_id: this.makeEventId(),
      run_id: task.run_id,
      type: "ArtifactCreated",
      phase: "applied",
      agent: this.agentId,
      artifact: this.makeArtifactRef({
        name: "execute_ops_report",
        path: `${runDir}/execute_ops_report.json`,
        schema: "execute_report.v1",
      }),
      timestamp: this.now(),
      prev_revision: task.input_state_revision,
      next_revision: task.input_state_revision + 1,
    })

    events.push({
      event_id: this.makeEventId(),
      run_id: task.run_id,
      type: checkResult.passed ? "ValidationPassed" : "ValidationFailed",
      phase: "applied",
      check_type: "execution",
      result: checkResult,
      timestamp: this.now(),
      prev_revision: task.input_state_revision + 1,
      next_revision: task.input_state_revision + 2,
    })

    if (buildStatus !== "completed") {
      return {
        ok: false,
        events,
        error: this.makeError(
          `Build ${buildStatus}: ${opsReport?.failed || 0} ops failed`,
          "EXECUTE_PARTIAL",
        ),
      }
    }

    return {
      ok: true,
      events,
      summary: `Applied ${opsReport?.succeeded || 0} ops successfully`,
    }
  }
}
