import type { AgentTask, AgentResult } from "./base"
import { BaseAgent } from "./base"
import type { PipelineState, CheckResult } from "../state/pipeline-state"
import type { PipelineEvent } from "../state/events"
import { spawnPython, readJsonFile } from "../pipeline-core"

export class QAAgent extends BaseAgent {
  readonly agentId = "QAAgent"
  readonly phase = "qa" as const

  async execute(task: AgentTask, state: PipelineState): Promise<AgentResult> {
    const events: PipelineEvent[] = []
    const runDir = task.run_dir

    const result = await spawnPython("qa_docx.py", ["--run-dir", runDir])

    const qaReport = await readJsonFile(`${runDir}/qa_report.json`).catch(() => null)

    const checkResult: CheckResult = {
      passed: !!qaReport && result.exit_code === 0,
      details: qaReport || {},
      errors: qaReport?.errors || [],
      warnings: qaReport?.warnings || [],
    }

    events.push({
      event_id: this.makeEventId(),
      run_id: task.run_id,
      type: "ArtifactCreated",
      phase: "qa_passed",
      agent: this.agentId,
      artifact: this.makeArtifactRef({
        name: "qa_report",
        path: `${runDir}/qa_report.json`,
        schema: "qa_report.v1",
      }),
      timestamp: this.now(),
      prev_revision: task.input_state_revision,
      next_revision: task.input_state_revision + 1,
    })

    events.push({
      event_id: this.makeEventId(),
      run_id: task.run_id,
      type: checkResult.passed ? "ValidationPassed" : "ValidationFailed",
      phase: "qa_passed",
      check_type: "qa",
      result: checkResult,
      timestamp: this.now(),
      prev_revision: task.input_state_revision + 1,
      next_revision: task.input_state_revision + 2,
    })

    return { ok: true, events, summary: "QA complete" }
  }
}
