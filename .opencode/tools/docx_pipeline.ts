import { tool } from "@opencode-ai/plugin"
import {
  parseMarkdownHeadings,
  readJsonFile,
  resolveInspectionRunDir,
  resolveRunDirArtifact,
  resolveWorkspacePath,
  runSteps,
  type ScriptStep,
} from "../../mcp/pipeline-core"

export const inspectTemplate = tool({
  // @ts-expect-error title is spec 2025-11-25, not yet in opencode plugin types
  title: "DOCX Template Inspector",
  description: `Read-only raw inspection of a DOCX template for LLM reasoning.

Writes {run_dir}/docx_inspect_output.json (combined), plus layer files:
- docx_inspect_paragraph_sample.json: first 30 paragraphs (quick reference)
- docx_inspect_all_para_ids.json: ALL paragraph paraIds (full document, use for anchor references)
- docx_inspect_styles_for_llm.json: compact style summary for LLM reasoning
- docx_inspect_content_map.json: front-matter/body anchor map

Schema: styles_raw (with outline_level_xml), paragraph_sample, all_para_ids,
page_layout_raw (twips), toc_entries_raw, front_matter_boundary, styles_for_llm, content_map.

Anchor format: /body/p[@paraId=XXXX] where XXXX is from all_para_ids.

CALL ORDER: Must be called BEFORE validateExecutionOps and applyExecutionOps.
Safe to call multiple times (idempotent).

ANNOTATIONS: read-only, idempotent, local filesystem only.`,
  annotations: {
    readOnlyHint: true,
    destructiveHint: false,
    idempotentHint: true,
    openWorldHint: false,
  },
  outputSchema: {
    type: "object" as const,
    properties: {
      ok: { type: "boolean" },
      script: { type: "string" },
      command: { type: "string" },
      stdout: { type: "string" },
      stderr: { type: "string" },
      exitCode: { type: "number" },
      run_dir: { type: "string" },
      inspection_file: { type: "string" },
      inspection: {
        type: "object",
        properties: {
          status: { type: "string" },
          template_file: { type: "string" },
          run_dir: { type: "string" },
          styles: { type: "array", items: { type: "object" } },
          anchors: { type: "array", items: { type: "object" } },
          fields: { type: "array", items: { type: "object" } },
        },
      },
    },
    required: ["ok", "inspection_file", "run_dir"],
  },
  args: {
    run_dir: tool.schema.string().default("").describe("Run directory path under .office-auto/state/. If omitted or shell-like, a new run dir is generated automatically."),
    template_file: tool.schema.string().describe("Absolute or relative path to the .docx template file to inspect."),
  },
  async execute(args, context) {
    const absRunDir = resolveInspectionRunDir(context.worktree, args.run_dir)
    const absTplFile = resolveWorkspacePath(context.worktree, args.template_file)
    const result = await runSteps(
      [["docx_inspect.py", ["--template-file", absTplFile, "--run-dir", absRunDir]]],
      context.worktree,
    )
    // New schema: read from docx_inspect_output.json (combined output)
    const payload = await readJsonFile(`${absRunDir}/docx_inspect_output.json`)
    return JSON.stringify(
      {
        ...result,
        run_dir: absRunDir,
        inspection_file: `${absRunDir}/docx_inspect_output.json`,
        inspection: payload ? { ...payload, run_dir: absRunDir } : payload,
      },
      null,
      2,
    )
  },
})

export const validateExecutionOps = tool({
  // @ts-expect-error title is spec 2025-11-25, not yet in opencode plugin types
  title: "DOCX Execution Ops Validator",
  description: `Validate LLM-generated execution_ops.json against raw template inspection.

Validates anchors against ALL paragraph paraIds (all_para_ids), not just the first 30.
Anchor conventions: "PREVIOUS" (sequential, always valid) or "/body/p[@paraId=XXXX]" (explicit, validated).

PRECONDITIONS: {run_dir}/docx_inspect_output.json must exist.
POSTCONDITIONS: Writes {run_dir}/execution_ops_validation.json.

CALL ORDER: AFTER inspectTemplate, BEFORE applyExecutionOps.
If warnings present, fix execution_ops.json and re-validate.

ANNOTATIONS: read-only, idempotent, local filesystem only.`,
  annotations: {
    readOnlyHint: true,
    destructiveHint: false,
    idempotentHint: true,
    openWorldHint: false,
  },
  outputSchema: {
    type: "object" as const,
    properties: {
      ok: { type: "boolean" },
      script: { type: "string" },
      command: { type: "string" },
      stdout: { type: "string" },
      stderr: { type: "string" },
      exitCode: { type: "number" },
      validation_file: { type: "string" },
      validation: {
        type: "object",
        properties: {
          status: { type: "string" },
          is_valid: { type: "boolean" },
          warnings: { type: "array", items: { type: "string" } },
          errors: { type: "array", items: { type: "string" } },
          ops_checked: { type: "number" },
        },
      },
    },
    required: ["ok", "validation_file"],
  },
  args: {
    run_dir: tool.schema.string().describe("Run directory under .office-auto/state/."),
    ops_file: tool.schema.string().default("").describe("Absolute or relative path to execution_ops.json. If omitted, defaults to {run_dir}/execution_ops.json."),
    strict_mode: tool.schema.boolean().default(false).describe("If true, warnings are treated as errors."),
  },
  async execute(args, context) {
    const absRunDir = resolveWorkspacePath(context.worktree, args.run_dir)
    const absOpsFile = resolveRunDirArtifact(absRunDir, args.ops_file, "execution_ops.json")
    const validateArgs = ["--run-dir", absRunDir, "--ops-file", absOpsFile]
    if (args.strict_mode) {
      validateArgs.push("--strict")
    }
    const result = await runSteps(
      [["docx_validate_ops.py", validateArgs]],
      context.worktree,
    )
    const payload = await readJsonFile(`${absRunDir}/execution_ops_validation.json`)
    return JSON.stringify(
      {
        ...result,
        validation_file: `${absRunDir}/execution_ops_validation.json`,
        validation: payload,
      },
      null,
      2,
    )
  },
})

export const applyExecutionOps = tool({
  // @ts-expect-error title is spec 2025-11-25, not yet in opencode plugin types
  title: "DOCX Execution Ops Apply",
  description: `Mechanical apply of execution_ops.json to a DOCX template, producing a built report DOCX.

Anchor conventions: "/body/p[@paraId=XXXX]" (explicit) or "PREVIOUS" (sequential, inserts after last op's result).
Standard pattern: first op uses explicit paraId, subsequent ops use "PREVIOUS".

PRECONDITIONS: {run_dir}/execution_ops.json must exist. template_file must be valid .docx.
execution_ops.json is resolved by convention from run_dir; do not point this tool at a different ops path unless you are intentionally overriding the convention.
POSTCONDITIONS: Writes {run_dir}/build_report.json, {run_dir}/execute_ops_report.json, and target_file.

CALL ORDER: AFTER validateExecutionOps and inspectTemplate.
Modes: 'full' (re-inspect), 'incremental' (skip if output exists), 'ops_only' (execute only).

ANNOTATIONS: writes output DOCX, non-idempotent.`,
  annotations: {
    readOnlyHint: false,
    destructiveHint: false,
    idempotentHint: false,
    openWorldHint: false,
  },
  outputSchema: {
    type: "object" as const,
    properties: {
      ok: { type: "boolean" },
      script: { type: "string" },
      command: { type: "string" },
      stdout: { type: "string" },
      stderr: { type: "string" },
      exitCode: { type: "number" },
      failed_step: { type: "string", description: "Name of failed script if status=failed" },
      mode: { type: "string", enum: ["full", "incremental", "ops_only"] },
      build_report_file: { type: "string" },
      build_report: {
        type: "object",
        properties: {
          status: { type: "string", enum: ["completed", "failed"] },
          ops_applied: { type: "number" },
          warnings: { type: "array", items: { type: "string" } },
          output_file: { type: "string" },
        },
      },
    },
    required: ["ok", "build_report_file"],
  },
  args: {
    run_dir: tool.schema.string().describe("Run directory under .office-auto/state/."),
    template_file: tool.schema.string().describe("Absolute or relative path to the .docx template file."),
    ops_file: tool.schema.string().default("").describe("Absolute or relative path to execution_ops.json. If omitted, defaults to {run_dir}/execution_ops.json."),
    target_file: tool.schema.string().describe("Absolute or relative path for the output .docx file."),
    source_file: tool.schema.string().default("").describe("Optional source markdown path."),
    mode: tool.schema
      .enum(["full", "incremental", "ops_only"])
      .default("full")
      .describe("'full' re-inspects; 'incremental' skips if output exists; 'ops_only' executes only."),
  },
  async execute(args, context) {
    const absRunDir = resolveWorkspacePath(context.worktree, args.run_dir)
    const absTplFile = resolveWorkspacePath(context.worktree, args.template_file)
    const absOpsFile = resolveRunDirArtifact(absRunDir, args.ops_file, "execution_ops.json")
    const absTargetFile = resolveWorkspacePath(context.worktree, args.target_file)
    const compileArgs = ["--run-dir", absRunDir, "--ops-file", absOpsFile, "--template-file", absTplFile, "--target-file", absTargetFile]
    if (args.source_file) {
      compileArgs.push("--source-file", resolveWorkspacePath(context.worktree, args.source_file))
    }

    // Determine steps based on mode
    const steps: ScriptStep[] = []
    const mode = args.mode || "full"

    if (mode === "full") {
      // Full mode: always re-inspect
      steps.push(["docx_inspect.py", ["--template-file", absTplFile, "--run-dir", absRunDir]])
    } else if (mode === "incremental") {
      // Incremental: skip re-inspect if docx_inspect_output.json already exists
      const inspectionPath = `${absRunDir}/docx_inspect_output.json`
      try {
        await new Response((globalThis as any).Bun.file(inspectionPath)).text()
        // File exists, skip inspect
      } catch {
        // File doesn't exist, fall back to full re-inspect
        steps.push(["docx_inspect.py", ["--template-file", absTplFile, "--run-dir", absRunDir]])
      }
    }
    // ops_only: skip inspect entirely

    // Single executor script handles compile + build + post_process
    steps.push(["execute_execution_ops.py", ["--run-dir", absRunDir]])

    const result = await runSteps(steps, context.worktree)
    const buildReport = await readJsonFile(`${absRunDir}/build_report.json`)
    let qaReport: any = undefined
    let reviewReport: any = undefined
    if (result.status === "completed") {
      const qaSteps: ScriptStep[] = [
        ["qa_docx.py", ["--run-dir", absRunDir]],
        ["review_docx.py", ["--run-dir", absRunDir]],
      ]
      const qaResult = await runSteps(qaSteps, context.worktree)
      if (qaResult.status !== "completed") {
        return JSON.stringify(
          {
            ...result,
            ...qaResult,
            mode: mode,
            build_report_file: `${absRunDir}/build_report.json`,
            build_report: buildReport,
            qa_file: `${absRunDir}/qa_report.json`,
            review_file: `${absRunDir}/review_report.json`,
          },
          null,
          2,
        )
      }
      qaReport = await readJsonFile(`${absRunDir}/qa_report.json`)
      reviewReport = await readJsonFile(`${absRunDir}/review_report.json`)
    }
    return JSON.stringify(
      {
        ...result,
        mode: mode,
        build_report_file: `${absRunDir}/build_report.json`,
        build_report: buildReport,
        qa_file: `${absRunDir}/qa_report.json`,
        qa_report: qaReport,
        review_file: `${absRunDir}/review_report.json`,
        review_report: reviewReport,
      },
      null,
      2,
    )
  },
})

export const prepareInsertPlan = tool({
  // @ts-expect-error title is spec 2025-11-25, not yet in opencode plugin types
  title: "DOCX Insert Plan Scaffold",
  description: `Aggregate inspection output and source markdown into a compact reasoning scaffold.

Reads docx_inspect_output.json, docx_inspect_styles_for_llm.json, and docx_inspect_content_map.json from run_dir.
Also parses the source markdown headings so the LLM can fill content with fewer context hops.

ANNOTATIONS: read-only, idempotent, local filesystem only.`,
  annotations: {
    readOnlyHint: true,
    destructiveHint: false,
    idempotentHint: true,
    openWorldHint: false,
  },
  outputSchema: {
    type: "object" as const,
    properties: {
      ok: { type: "boolean" },
      scaffold_file: { type: "string" },
      scaffold: { type: "object" },
    },
    required: ["ok", "scaffold_file"],
  },
  args: {
    run_dir: tool.schema.string().describe("Run directory containing inspection artifacts."),
    content_file: tool.schema.string().default("").describe("Path to the source markdown file. If omitted, the scaffold only includes inspection artifacts."),
  },
  async execute(args, context) {
    const absRunDir = resolveWorkspacePath(context.worktree, args.run_dir)
    const contentFile = args.content_file ? resolveWorkspacePath(context.worktree, args.content_file) : ""
    const inspection = await readJsonFile(`${absRunDir}/docx_inspect_output.json`)
    const stylesForLlm = await readJsonFile(`${absRunDir}/docx_inspect_styles_for_llm.json`)
    const contentMap = await readJsonFile(`${absRunDir}/docx_inspect_content_map.json`)
    let headings: Array<{ level: number; text: string }> = []
    if (contentFile) {
      try {
        const markdownText = await new Response((globalThis as any).Bun.file(contentFile)).text()
        headings = parseMarkdownHeadings(markdownText)
      } catch {
        headings = []
      }
    }

    const scaffold = {
      run_dir: absRunDir,
      source_file: contentFile || null,
      recommended_anchor: contentMap?.recommended_insert_anchor || stylesForLlm?.recommended_anchor || inspection?.content_map?.recommended_insert_anchor || null,
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
    await (globalThis as any).Bun.write(scaffoldFile, JSON.stringify(scaffold, null, 2) + "\n")
    return JSON.stringify(
      {
        ok: true,
        scaffold_file: scaffoldFile,
        scaffold,
      },
      null,
      2,
    )
  },
})

export const reviewOutput = tool({
  // @ts-expect-error title is spec 2025-11-25, not yet in opencode plugin types
  title: "DOCX Output Reviewer",
  description: `Run semantic review of the generated DOCX and expose review artifacts.

Wraps review_docx.py and returns review_report.json plus markdown/html artifacts.
Call after applyExecutionOps or runPipeline to verify output quality before finalizing.

ANNOTATIONS: read-only, idempotent, local filesystem only.`,
  annotations: {
    readOnlyHint: true,
    destructiveHint: false,
    idempotentHint: true,
    openWorldHint: false,
  },
  outputSchema: {
    type: "object" as const,
    properties: {
      ok: { type: "boolean" },
      script: { type: "string" },
      command: { type: "string" },
      stdout: { type: "string" },
      stderr: { type: "string" },
      exitCode: { type: "number" },
      review_file: { type: "string" },
      review_report: { type: "object" },
      review_markdown_file: { type: "string" },
      review_html_file: { type: "string" },
    },
    required: ["ok", "review_file"],
  },
  args: {
    run_dir: tool.schema.string().describe("Run directory containing build_report.json and review inputs."),
  },
  async execute(args, context) {
    const absRunDir = resolveWorkspacePath(context.worktree, args.run_dir)
    const result = await runSteps([["review_docx.py", ["--run-dir", absRunDir]]], context.worktree)
    const payload = await readJsonFile(`${absRunDir}/review_report.json`)
    return JSON.stringify(
      {
        ...result,
        review_file: `${absRunDir}/review_report.json`,
        review_report: payload,
        review_markdown_file: `${absRunDir}/review_report.md`,
        review_html_file: `${absRunDir}/review_screen.html`,
      },
      null,
      2,
    )
  },
})

export const readResult = tool({
  // @ts-expect-error title is spec 2025-11-25, not yet in opencode plugin types
  title: "DOCX Result Reader",
  description: `Read a built DOCX back into text/structure summaries for LLM verification.

PRECONDITIONS:
- {run_dir}/build_report.json must exist with status=completed (run applyExecutionOps first).
- The target DOCX file must exist at the expected output path.

POSTCONDITIONS:
- Writes: {run_dir}/result_readback.json (headings, body text, TOC, fields summary).
- Returns: JSON with readback status + structured result payload.

CALL ORDER:
- Must be called AFTER applyExecutionOps.
- Use this to verify output correctness before declaring a run complete.
- Hard gate: do not mark task as complete without successful readback verification.

ANNOTATIONS: read-only, idempotent, local filesystem only.`,
  annotations: {
    readOnlyHint: true,
    destructiveHint: false,
    idempotentHint: true,
    openWorldHint: false,
  },
  outputSchema: {
    type: "object" as const,
    properties: {
      ok: { type: "boolean" },
      script: { type: "string" },
      command: { type: "string" },
      stdout: { type: "string" },
      stderr: { type: "string" },
      exitCode: { type: "number" },
      result_file: { type: "string" },
      result: {
        type: "object",
        properties: {
          status: { type: "string" },
          file: { type: "string" },
          headings: { type: "array", items: { type: "object" } },
          body: { type: "array", items: { type: "object" } },
          toc: { type: "array", items: { type: "object" } },
          fields: { type: "array", items: { type: "object" } },
        },
      },
    },
    required: ["ok", "result_file"],
  },
  args: {
    run_dir: tool.schema.string().describe("Run directory under .office-auto/state/ where build_report.json and the output DOCX reside."),
    target_file: tool.schema.string().default("").describe("Optional absolute or relative path override for the target DOCX file to read."),
    sections: tool.schema
      .array(tool.schema.string())
      .default([])
      .describe("Optional list of section names/keys to filter the readback. Empty array returns full result."),
  },
  async execute(args, context) {
    const absRunDir = resolveWorkspacePath(context.worktree, args.run_dir)
    const steps: ScriptStep[] = [["docx_read_result.py", ["--run-dir", absRunDir]]]
    if (args.target_file) {
      steps[0][1].push("--file", resolveWorkspacePath(context.worktree, args.target_file))
    }
    if (args.sections && args.sections.length > 0) {
      for (const section of args.sections) {
        steps[0][1].push("--section", section)
      }
    }
    const result = await runSteps(steps, context.worktree)
    const payload = await readJsonFile(`${absRunDir}/result_readback.json`)
    return JSON.stringify(
      {
        ...result,
        result_file: `${absRunDir}/result_readback.json`,
        result: payload,
      },
      null,
      2,
    )
  },
})

export const runPipeline = tool({
  // @ts-expect-error title is spec 2025-11-25, not yet in opencode plugin types
  title: "DOCX Pipeline Runner",
  description: `Composite tool: inspect → validate → apply → read.

Use phases=["all"] for full pipeline, or custom array for partial runs.
Prefer individual tools when you need to inspect intermediate outputs.

PRECONDITIONS: execution_ops.json for validate/apply; template_file for inspect; build_report.json for read.
POSTCONDITIONS: All intermediate artifacts for each phase.

ANNOTATIONS: writes output artifacts, non-idempotent.`,
  annotations: {
    readOnlyHint: false,
    destructiveHint: false,
    idempotentHint: false,
    openWorldHint: false,
  },
  outputSchema: {
    type: "object" as const,
    properties: {
      status: { type: "string", enum: ["completed", "failed"] },
      phases_run: { type: "array", items: { type: "string" } },
      phases_status: {
        type: "object",
        additionalProperties: {
          type: "object",
          properties: {
            status: { type: "string", enum: ["completed", "failed", "skipped"] },
            script: { type: "string" },
            exitCode: { type: "number" },
          },
        },
      },
      artifacts: {
        type: "object",
        properties: {
          inspection_file: { type: "string" },
          validation_file: { type: "string" },
          build_report_file: { type: "string" },
          result_file: { type: "string" },
          qa_file: { type: "string" },
          review_file: { type: "string" },
        },
      },
      failed_phase: { type: "string", description: "Name of first failed phase, if any" },
    },
    required: ["status", "phases_run"],
  },
  args: {
    run_dir: tool.schema.string().describe("Run directory under .office-auto/state/."),
    template_file: tool.schema.string().describe("Absolute or relative path to the .docx template file."),
    ops_file: tool.schema.string().describe("Absolute or relative path to the LLM-generated execution_ops.json file."),
    target_file: tool.schema.string().describe("Absolute or relative path for the output .docx file."),
    source_file: tool.schema.string().default("").describe("Optional source markdown path, recorded in plan/run artifacts only."),
    phases: tool.schema
      .array(tool.schema.enum(["inspect", "validate", "apply", "read", "all"]))
      .default(["all"])
      .describe("Phases to run. 'all' = inspect+validate+apply+read in order."),
    mode: tool.schema
      .enum(["full", "incremental", "ops_only"])
      .default("full")
      .describe("Build mode for the apply phase (see apply_execution_ops for details)."),
  },
  async execute(args, context) {
    const absRunDir = resolveWorkspacePath(context.worktree, args.run_dir)
    const absTplFile = resolveWorkspacePath(context.worktree, args.template_file)
    const absOpsFile = resolveRunDirArtifact(absRunDir, args.ops_file, "execution_ops.json")
    const absTargetFile = resolveWorkspacePath(context.worktree, args.target_file)
    const absSourceFile = args.source_file ? resolveWorkspacePath(context.worktree, args.source_file) : ""

    // Resolve phases: expand "all"
    let phases = args.phases || ["all"]
    if (phases.includes("all")) {
      phases = ["inspect", "validate", "apply", "read"]
    }

    const phasesStatus: Record<string, any> = {}
    const artifacts: Record<string, string> = {}
    let overallStatus: "completed" | "failed" = "completed"
    let failedPhase: string | undefined

    for (const phase of phases) {
      if (phase === "inspect") {
        const inspectResult = await runSteps(
          [["docx_inspect.py", ["--template-file", absTplFile, "--run-dir", absRunDir]]],
          context.worktree,
        )
        phasesStatus["inspect"] = { status: inspectResult.status, script: "docx_inspect.py", exitCode: inspectResult.results[0]?.exitCode ?? 0 }
        if (inspectResult.status !== "completed") {
          overallStatus = "failed"
          failedPhase = "inspect"
          break
        }
        artifacts.inspection_file = `${absRunDir}/docx_inspect_output.json`
      } else if (phase === "validate") {
        const validateArgs = ["--run-dir", absRunDir, "--ops-file", absOpsFile]
        const validateResult = await runSteps(
          [["docx_validate_ops.py", validateArgs]],
          context.worktree,
        )
        phasesStatus["validate"] = { status: validateResult.status, script: "docx_validate_ops.py", exitCode: validateResult.results[0]?.exitCode ?? 0 }
        if (validateResult.status !== "completed") {
          overallStatus = "failed"
          failedPhase = "validate"
          break
        }
        artifacts.validation_file = `${absRunDir}/execution_ops_validation.json`
      } else if (phase === "apply") {
        const applySteps: ScriptStep[] = []
        const mode = args.mode || "full"

        if (mode === "full") {
          applySteps.push(["docx_inspect.py", ["--template-file", absTplFile, "--run-dir", absRunDir]])
        } else if (mode === "incremental") {
          const inspectionPath = `${absRunDir}/docx_inspect_output.json`
          try {
            await new Response((globalThis as any).Bun.file(inspectionPath)).text()
          } catch {
            applySteps.push(["docx_inspect.py", ["--template-file", absTplFile, "--run-dir", absRunDir]])
          }
        }

        // Single executor script handles compile + build + post_process
        applySteps.push(["execute_execution_ops.py", ["--run-dir", absRunDir]])

        const applyResult = await runSteps(applySteps, context.worktree)
        phasesStatus["apply"] = { status: applyResult.status, script: applyResult.failed_step || "execute_execution_ops.py", exitCode: applyResult.results[applyResult.results.length - 1]?.exitCode ?? 0 }
        if (applyResult.status !== "completed") {
          overallStatus = "failed"
          failedPhase = "apply"
          break
        }
        artifacts.build_report_file = `${absRunDir}/build_report.json`
        const qaResult = await runSteps(
          [["qa_docx.py", ["--run-dir", absRunDir]], ["review_docx.py", ["--run-dir", absRunDir]]],
          context.worktree,
        )
        phasesStatus["qa"] = { status: qaResult.results[0]?.ok ? "completed" : "failed", script: "qa_docx.py", exitCode: qaResult.results[0]?.exitCode ?? 0 }
        if (qaResult.results[1]) {
          phasesStatus["review"] = { status: qaResult.results[1].ok ? "completed" : "failed", script: "review_docx.py", exitCode: qaResult.results[1]?.exitCode ?? 0 }
        }
        if (qaResult.status !== "completed") {
          overallStatus = "failed"
          failedPhase = qaResult.failed_step === "review_docx.py" ? "review" : "qa"
          break
        }
        artifacts.qa_file = `${absRunDir}/qa_report.json`
        artifacts.review_file = `${absRunDir}/review_report.json`
      } else if (phase === "read") {
        const readArgs = ["--run-dir", absRunDir]
        if (absTargetFile) {
          readArgs.push("--file", absTargetFile)
        }
        const readResult = await runSteps(
          [["docx_read_result.py", readArgs]],
          context.worktree,
        )
        phasesStatus["read"] = { status: readResult.status, script: "docx_read_result.py", exitCode: readResult.results[0]?.exitCode ?? 0 }
        if (readResult.status !== "completed") {
          overallStatus = "failed"
          failedPhase = "read"
          break
        }
        artifacts.result_file = `${absRunDir}/result_readback.json`
      }
    }

    return JSON.stringify(
      {
        status: overallStatus,
        phases_run: phases,
        phases_status: phasesStatus,
        artifacts: artifacts,
        failed_phase: failedPhase,
      },
      null,
      2,
    )
  },
})
