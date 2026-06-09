import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js"
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js"
import { z } from "zod"
import {
  fileExists,
  parseMarkdownHeadings,
  readJsonFile,
  readTextFile,
  resolveInspectionRunDir,
  resolveRunDirArtifact,
  resolveWorkspacePath,
  runSteps,
  writeJsonFile,
  type ScriptStep,
} from "./pipeline-core"

const WORKTREE = process.env.OFFICE_AUTO_WORKSPACE ?? process.cwd()
const server = new McpServer({ name: "office-auto", version: "1.0.0" })

function jsonToolResult(output: Record<string, unknown>) {
  return {
    content: [{ type: "text" as const, text: JSON.stringify(output, null, 2) }],
    structuredContent: output,
  }
}

server.registerTool(
  "inspectTemplate",
  {
    title: "DOCX Template Inspector",
    description:
      "Read-only raw inspection of a DOCX template for LLM reasoning. Writes docx_inspect_output.json and the layer artifacts required for the DOCX pipeline.",
    inputSchema: z.object({
      run_dir: z.string(),
      template_file: z.string(),
    }),
    annotations: { readOnlyHint: true, idempotentHint: true, openWorldHint: false },
  },
  async ({ run_dir, template_file }) => {
    const absRunDir = resolveInspectionRunDir(WORKTREE, run_dir)
    const absTpl = resolveWorkspacePath(WORKTREE, template_file)
    const result = await runSteps(
      [["docx_inspect.py", ["--template-file", absTpl, "--run-dir", absRunDir]]],
      WORKTREE,
    )
    const payload = await readJsonFile(`${absRunDir}/docx_inspect_output.json`)
    const compactInspection = payload ? {
      status: "completed",
      template_file: absTpl,
      run_dir: absRunDir,
      recommended_anchor: payload.content_map?.recommended_insert_anchor || payload.styles_for_llm?.recommended_anchor || null,
      body_text_style: payload.styles_for_llm?.body_text_style || null,
      heading_map: payload.styles_for_llm?.heading_map || {},
      do_not_use_styles: payload.styles_for_llm?.do_not_use_styles || [],
      front_matter_boundary: payload.front_matter_boundary || {},
      available_styles: (payload.styles_for_llm?.available_styles || []).slice(0, 15).map((s: any) => ({
        name: s.name,
        style_id: s.style_id,
        use_for: s.use_for
      })),
      placeholders: (payload.all_para_ids || [])
        .filter((p: any) => !p.is_front_matter)
        .map((p: any) => ({
          paraId: p.para_id,
          text_preview: p.text_preview
        }))
    } : null;

    const output = {
      ...result,
      run_dir: absRunDir,
      inspection_file: `${absRunDir}/docx_inspect_output.json`,
      inspection: compactInspection,
    }
    return jsonToolResult(output)
  },
)

server.registerTool(
  "validateExecutionOps",
  {
    title: "DOCX Execution Ops Validator",
    description:
      "Validate execution_ops.json against the latest template inspection. Writes execution_ops_validation.json and warns on anchor/style issues.",
    inputSchema: z.object({
      run_dir: z.string(),
      ops_file: z.string().default(""),
      strict_mode: z.boolean().default(false),
    }),
    annotations: { readOnlyHint: true, idempotentHint: true, openWorldHint: false },
  },
  async ({ run_dir, ops_file, strict_mode }) => {
    const absRunDir = resolveWorkspacePath(WORKTREE, run_dir)
    const absOpsFile = resolveRunDirArtifact(absRunDir, ops_file, "execution_ops.json")
    const validateArgs = ["--run-dir", absRunDir, "--ops-file", absOpsFile]
    if (strict_mode) {
      validateArgs.push("--strict")
    }
    const result = await runSteps([["docx_validate_ops.py", validateArgs]], WORKTREE)
    const validation = await readJsonFile(`${absRunDir}/execution_ops_validation.json`)
    return jsonToolResult({
      ...result,
      validation_file: `${absRunDir}/execution_ops_validation.json`,
      validation,
    })
  },
)

server.registerTool(
  "applyExecutionOps",
  {
    title: "DOCX Execution Ops Apply",
    description:
      "Mechanical apply of execution_ops.json to a DOCX template, producing the output report and post-build QA/review artifacts.",
    inputSchema: z.object({
      run_dir: z.string(),
      template_file: z.string(),
      ops_file: z.string().default(""),
      target_file: z.string(),
      source_file: z.string().default(""),
      mode: z.enum(["full", "incremental", "ops_only"]).default("full"),
    }),
    annotations: { readOnlyHint: false, idempotentHint: false, openWorldHint: false },
  },
  async ({ run_dir, template_file, ops_file, target_file, source_file, mode }) => {
    const absRunDir = resolveWorkspacePath(WORKTREE, run_dir)
    const absTplFile = resolveWorkspacePath(WORKTREE, template_file)
    const absOpsFile = resolveRunDirArtifact(absRunDir, ops_file, "execution_ops.json")
    const absTargetFile = resolveWorkspacePath(WORKTREE, target_file)

    const steps: ScriptStep[] = []
    if (mode === "full") {
      steps.push(["docx_inspect.py", ["--template-file", absTplFile, "--run-dir", absRunDir]])
    } else if (mode === "incremental") {
      const inspectionPath = `${absRunDir}/docx_inspect_output.json`
      if (!(await fileExists(inspectionPath))) {
        steps.push(["docx_inspect.py", ["--template-file", absTplFile, "--run-dir", absRunDir]])
      }
    }
    steps.push(["execute_execution_ops.py", ["--run-dir", absRunDir]])

    const result = await runSteps(steps, WORKTREE)
    const buildReport = await readJsonFile(`${absRunDir}/build_report.json`)
    let qaReport: any = undefined
    let reviewReport: any = undefined

    if (result.status === "completed") {
      const qaResult = await runSteps(
        [["qa_docx.py", ["--run-dir", absRunDir]], ["review_docx.py", ["--run-dir", absRunDir]]],
        WORKTREE,
      )
      if (qaResult.status === "completed") {
        qaReport = await readJsonFile(`${absRunDir}/qa_report.json`)
        reviewReport = await readJsonFile(`${absRunDir}/review_report.json`)
      } else {
        return jsonToolResult({
          ...result,
          ...qaResult,
          mode,
          build_report_file: `${absRunDir}/build_report.json`,
          build_report: buildReport,
          qa_file: `${absRunDir}/qa_report.json`,
          review_file: `${absRunDir}/review_report.json`,
        })
      }
    }

    return jsonToolResult({
      ...result,
      mode,
      build_report_file: `${absRunDir}/build_report.json`,
      build_report: buildReport,
      qa_file: `${absRunDir}/qa_report.json`,
      qa_report: qaReport,
      review_file: `${absRunDir}/review_report.json`,
      review_report: reviewReport,
    })
  },
)

server.registerTool(
  "prepareInsertPlan",
  {
    title: "DOCX Insert Plan Scaffold",
    description:
      "Aggregate inspection output and source markdown headings into a compact reasoning scaffold for execution planning.",
    inputSchema: z.object({
      run_dir: z.string(),
      content_file: z.string().default(""),
    }),
    annotations: { readOnlyHint: true, idempotentHint: true, openWorldHint: false },
  },
  async ({ run_dir, content_file }) => {
    const absRunDir = resolveWorkspacePath(WORKTREE, run_dir)
    const contentFile = content_file ? resolveWorkspacePath(WORKTREE, content_file) : ""
    const inspection = await readJsonFile(`${absRunDir}/docx_inspect_output.json`)
    const stylesForLlm = await readJsonFile(`${absRunDir}/docx_inspect_styles_for_llm.json`)
    const contentMap = await readJsonFile(`${absRunDir}/docx_inspect_content_map.json`)
    let headings: Array<{ level: number; text: string }> = []
    if (contentFile) {
      try {
        const markdownText = await readTextFile(contentFile)
        headings = parseMarkdownHeadings(markdownText)
      } catch {
        headings = []
      }
    }

    const scaffold = {
      run_dir: absRunDir,
      source_file: contentFile || null,
      recommended_anchor:
        contentMap?.recommended_insert_anchor ||
        stylesForLlm?.recommended_anchor ||
        inspection?.content_map?.recommended_insert_anchor ||
        null,
      body_text_style: stylesForLlm?.body_text_style || inspection?.styles_for_llm?.body_text_style || null,
      heading_map: stylesForLlm?.heading_map || inspection?.styles_for_llm?.heading_map || {},
      available_styles: stylesForLlm?.available_styles || inspection?.styles_for_llm?.available_styles || [],
      do_not_use_styles: stylesForLlm?.do_not_use_styles || inspection?.styles_for_llm?.do_not_use_styles || [],
      front_matter: contentMap?.front_matter || inspection?.content_map?.front_matter || {},
      body_placeholders: contentMap?.body_placeholders || inspection?.content_map?.body_placeholders || {},
      markdown_headings: headings,
      markdown_heading_count: headings.length,
      paragraph_count: Array.isArray(inspection?.paragraph_sample) ? inspection.paragraph_sample.length : 0,
    }

    const scaffoldFile = `${absRunDir}/insert_plan_scaffold.json`
    await writeJsonFile(scaffoldFile, scaffold)
    return jsonToolResult({
      ok: true,
      scaffold_file: scaffoldFile,
      scaffold,
    })
  },
)

server.registerTool(
  "reviewOutput",
  {
    title: "DOCX Output Reviewer",
    description: "Run semantic review of the generated DOCX and expose review artifacts.",
    inputSchema: z.object({
      run_dir: z.string(),
    }),
    annotations: { readOnlyHint: true, idempotentHint: true, openWorldHint: false },
  },
  async ({ run_dir }) => {
    const absRunDir = resolveWorkspacePath(WORKTREE, run_dir)
    const result = await runSteps([["review_docx.py", ["--run-dir", absRunDir]]], WORKTREE)
    const payload = await readJsonFile(`${absRunDir}/review_report.json`)
    return jsonToolResult({
      ...result,
      review_file: `${absRunDir}/review_report.json`,
      review_report: payload,
      review_markdown_file: `${absRunDir}/review_report.md`,
      review_html_file: `${absRunDir}/review_screen.html`,
    })
  },
)

server.registerTool(
  "readResult",
  {
    title: "DOCX Result Reader",
    description: "Read a built DOCX back into text and structure summaries for verification.",
    inputSchema: z.object({
      run_dir: z.string(),
      target_file: z.string().default(""),
      sections: z.array(z.string()).default([]),
    }),
    annotations: { readOnlyHint: true, idempotentHint: true, openWorldHint: false },
  },
  async ({ run_dir, target_file, sections }) => {
    const absRunDir = resolveWorkspacePath(WORKTREE, run_dir)
    const steps: ScriptStep = ["docx_read_result.py", ["--run-dir", absRunDir]]
    if (target_file) {
      steps[1].push("--file", resolveWorkspacePath(WORKTREE, target_file))
    }
    if (sections && sections.length > 0) {
      for (const section of sections) {
        steps[1].push("--section", section)
      }
    }
    const result = await runSteps([steps], WORKTREE)
    const payload = await readJsonFile(`${absRunDir}/result_readback.json`)
    return jsonToolResult({
      ...result,
      result_file: `${absRunDir}/result_readback.json`,
      result: payload,
    })
  },
)

server.registerTool(
  "runPipeline",
  {
    title: "DOCX Pipeline Runner",
    description: "Composite tool: inspect → validate → apply → read.",
    inputSchema: z.object({
      run_dir: z.string(),
      template_file: z.string(),
      ops_file: z.string(),
      target_file: z.string(),
      source_file: z.string().default(""),
      phases: z.array(z.enum(["inspect", "validate", "apply", "read", "all"])).default(["all"]),
      mode: z.enum(["full", "incremental", "ops_only"]).default("full"),
    }),
    annotations: { readOnlyHint: false, idempotentHint: false, openWorldHint: false },
  },
  async ({ run_dir, template_file, ops_file, target_file, source_file, phases, mode }) => {
    const absRunDir = resolveWorkspacePath(WORKTREE, run_dir)
    const absTplFile = resolveWorkspacePath(WORKTREE, template_file)
    const absOpsFile = resolveRunDirArtifact(absRunDir, ops_file, "execution_ops.json")
    const absTargetFile = resolveWorkspacePath(WORKTREE, target_file)

    let resolvedPhases = phases || ["all"]
    if (resolvedPhases.includes("all")) {
      resolvedPhases = ["inspect", "validate", "apply", "read"]
    }

    const phasesStatus: Record<string, any> = {}
    const artifacts: Record<string, string> = {}
    let overallStatus: "completed" | "failed" = "completed"
    let failedPhase: string | undefined

    for (const phase of resolvedPhases) {
      if (phase === "inspect") {
        const inspectResult = await runSteps(
          [["docx_inspect.py", ["--template-file", absTplFile, "--run-dir", absRunDir]]],
          WORKTREE,
        )
        phasesStatus.inspect = {
          status: inspectResult.status,
          script: "docx_inspect.py",
          exitCode: inspectResult.results[0]?.exitCode ?? 0,
        }
        if (inspectResult.status !== "completed") {
          overallStatus = "failed"
          failedPhase = "inspect"
          break
        }
        artifacts.inspection_file = `${absRunDir}/docx_inspect_output.json`
      } else if (phase === "validate") {
        const validateArgs = ["--run-dir", absRunDir, "--ops-file", absOpsFile]
        const validateResult = await runSteps([["docx_validate_ops.py", validateArgs]], WORKTREE)
        phasesStatus.validate = {
          status: validateResult.status,
          script: "docx_validate_ops.py",
          exitCode: validateResult.results[0]?.exitCode ?? 0,
        }
        if (validateResult.status !== "completed") {
          overallStatus = "failed"
          failedPhase = "validate"
          break
        }
        artifacts.validation_file = `${absRunDir}/execution_ops_validation.json`
      } else if (phase === "apply") {
        const applySteps: ScriptStep[] = []
        if (mode === "full") {
          applySteps.push(["docx_inspect.py", ["--template-file", absTplFile, "--run-dir", absRunDir]])
        } else if (mode === "incremental") {
          if (!(await fileExists(`${absRunDir}/docx_inspect_output.json`))) {
            applySteps.push(["docx_inspect.py", ["--template-file", absTplFile, "--run-dir", absRunDir]])
          }
        }
        applySteps.push(["execute_execution_ops.py", ["--run-dir", absRunDir]])

        const applyResult = await runSteps(applySteps, WORKTREE)
        phasesStatus.apply = {
          status: applyResult.status,
          script: applyResult.failed_step || "execute_execution_ops.py",
          exitCode: applyResult.results[applyResult.results.length - 1]?.exitCode ?? 0,
        }
        if (applyResult.status !== "completed") {
          overallStatus = "failed"
          failedPhase = "apply"
          break
        }
        artifacts.build_report_file = `${absRunDir}/build_report.json`
        const qaResult = await runSteps(
          [["qa_docx.py", ["--run-dir", absRunDir]], ["review_docx.py", ["--run-dir", absRunDir]]],
          WORKTREE,
        )
        phasesStatus.qa = {
          status: qaResult.results[0]?.ok ? "completed" : "failed",
          script: "qa_docx.py",
          exitCode: qaResult.results[0]?.exitCode ?? 0,
        }
        if (qaResult.results[1]) {
          phasesStatus.review = {
            status: qaResult.results[1].ok ? "completed" : "failed",
            script: "review_docx.py",
            exitCode: qaResult.results[1]?.exitCode ?? 0,
          }
        }
        if (qaResult.status !== "completed") {
          overallStatus = "failed"
          failedPhase = qaResult.failed_step === "review_docx.py" ? "review" : "qa"
          break
        }
        artifacts.qa_file = `${absRunDir}/qa_report.json`
        artifacts.review_file = `${absRunDir}/review_report.json`
      } else if (phase === "read") {
        const readSteps: ScriptStep[] = [["docx_read_result.py", ["--run-dir", absRunDir]]]
        if (absTargetFile) {
          readSteps[0][1].push("--file", absTargetFile)
        }
        const readResult = await runSteps(readSteps, WORKTREE)
        phasesStatus.read = {
          status: readResult.status,
          script: "docx_read_result.py",
          exitCode: readResult.results[0]?.exitCode ?? 0,
        }
        if (readResult.status !== "completed") {
          overallStatus = "failed"
          failedPhase = "read"
          break
        }
        artifacts.result_file = `${absRunDir}/result_readback.json`
      }
    }

    return jsonToolResult({
      status: overallStatus,
      phases_run: resolvedPhases,
      phases_status: phasesStatus,
      artifacts,
      failed_phase: failedPhase,
    })
  },
)

process.on("uncaughtException", (error) => {
  console.error(error)
  process.exit(1)
})

process.on("unhandledRejection", (error) => {
  console.error(error)
  process.exit(1)
})

try {
  process.stdin.resume()
  await server.connect(new StdioServerTransport())
  const keepAlive = setInterval(() => {}, 60_000)
  process.on("SIGINT", async () => {
    clearInterval(keepAlive)
    await server.close()
    process.exit(0)
  })
} catch (error) {
  console.error(error)
  process.exit(1)
}
