import type { AgentTask, AgentResult } from "./base"
import { BaseAgent } from "./base"
import type { PipelineState } from "../state/pipeline-state"
import type { PipelineEvent } from "../state/events"
import { readJsonFile, writeJsonFile } from "../pipeline-core"

export class MapperAgent extends BaseAgent {
  readonly agentId = "MapperAgent"
  readonly phase = "mapping" as const

  async execute(task: AgentTask, state: PipelineState): Promise<AgentResult> {
    const events: PipelineEvent[] = []
    const runDir = task.run_dir

    const stylesForLlm = await readJsonFile(`${runDir}/docx_inspect_styles_for_llm.json`).catch(() => ({}))
    const scaffold = await readJsonFile(`${runDir}/insert_plan_scaffold.json`).catch(() => ({}))

    const headingMap = scaffold?.heading_map || stylesForLlm?.heading_map || {}
    const bodyStyle = scaffold?.body_text_style || stylesForLlm?.body_text_style || "Normal"

    const styleMap = {
      h1: headingMap.h1 || "Heading1",
      h2: headingMap.h2 || "Heading2",
      h3: headingMap.h3 || "Heading3",
      body: bodyStyle,
      caption: "Caption",
      preserve_zones: ["front_matter", "toc", "headers_footers"],
    }

    const firstAnchor = scaffold?.CRITICAL_FIRST_OP_ANCHOR || scaffold?.recommended_anchor || ""
    const bodyParaIds: string[] = scaffold?.body_placeholders?.para_ids || []
    const removePaths = bodyParaIds
      .filter((pid: string) => pid)
      .map((pid: string) => `/body/p[@paraId=${pid}]`)

    const replaceRange = {
      insert_after_path: firstAnchor,
      remove_paths: removePaths,
      remove_rule: `Remove ${removePaths.length} body placeholders (all non-front-matter)`,
      preserve_zones: ["front_matter", "toc", "headers_footers"],
    }

    await writeJsonFile(`${runDir}/style_map.json`, styleMap)
    await writeJsonFile(`${runDir}/replace_range.json`, replaceRange)

    events.push({
      event_id: this.makeEventId(),
      run_id: task.run_id,
      type: "ArtifactCreated",
      phase: "mapped",
      agent: this.agentId,
      artifact: this.makeArtifactRef({
        name: "style_map",
        path: `${runDir}/style_map.json`,
        schema: "mapping.v1",
      }),
      timestamp: this.now(),
      prev_revision: task.input_state_revision,
      next_revision: task.input_state_revision + 1,
    })

    events.push({
      event_id: this.makeEventId(),
      run_id: task.run_id,
      type: "ArtifactCreated",
      phase: "mapped",
      agent: this.agentId,
      artifact: this.makeArtifactRef({
        name: "replace_range",
        path: `${runDir}/replace_range.json`,
        schema: "mapping.v1",
      }),
      timestamp: this.now(),
      prev_revision: task.input_state_revision + 1,
      next_revision: task.input_state_revision + 2,
    })

    events.push({
      event_id: this.makeEventId(),
      run_id: task.run_id,
      type: "DecisionRecorded",
      phase: "mapped",
      decision_type: "style_map",
      artifact: this.makeArtifactRef({
        name: "style_map",
        path: `${runDir}/style_map.json`,
      }),
      timestamp: this.now(),
      prev_revision: task.input_state_revision + 2,
      next_revision: task.input_state_revision + 3,
    })

    return { ok: true, events, summary: `Mapped ${Object.keys(headingMap).length} headings, ${removePaths.length} remove paths` }
  }
}
