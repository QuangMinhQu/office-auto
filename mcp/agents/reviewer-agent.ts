import type { AgentTask, AgentResult } from "./base"
import { BaseAgent } from "./base"
import type { PipelineState, CheckResult } from "../state/pipeline-state"
import type { PipelineEvent } from "../state/events"
import { spawnPython, readJsonFile } from "../pipeline-core"

export class ReviewerAgent extends BaseAgent {
  readonly agentId = "ReviewerAgent"
  readonly phase = "reviewing" as const

  async execute(task: AgentTask, state: PipelineState): Promise<AgentResult> {
    const events: PipelineEvent[] = []
    const runDir = task.run_dir

    const result = await spawnPython("review_docx.py", ["--run-dir", runDir])

    const reviewReport = await readJsonFile(`${runDir}/review_report.json`).catch(() => null)

    const checkResult: CheckResult = {
      passed: reviewReport?.passed === true || result.exit_code === 0,
      details: reviewReport || {},
      errors: reviewReport?.errors || [],
      warnings: reviewReport?.warnings || [],
    }

    events.push({
      event_id: this.makeEventId(),
      run_id: task.run_id,
      type: "ArtifactCreated",
      phase: "reviewed",
      agent: this.agentId,
      artifact: this.makeArtifactRef({
        name: "review_report",
        path: `${runDir}/review_report.json`,
        schema: "review_report.v1",
      }),
      timestamp: this.now(),
      prev_revision: task.input_state_revision,
      next_revision: task.input_state_revision + 1,
    })

    events.push({
      event_id: this.makeEventId(),
      run_id: task.run_id,
      type: checkResult.passed ? "ValidationPassed" : "ValidationFailed",
      phase: "reviewed",
      check_type: "review",
      result: checkResult,
      timestamp: this.now(),
      prev_revision: task.input_state_revision + 1,
      next_revision: task.input_state_revision + 2,
    })

    return { ok: true, events, summary: "Review complete" }
  }
}
