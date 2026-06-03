import { tool } from "@opencode-ai/plugin"

const BunRuntime = (globalThis as any).Bun as {
  spawn: (
    command: string[],
    opts: { cwd: string; stdout: "pipe"; stderr: "pipe" },
  ) => { stdout: ReadableStream<Uint8Array>; stderr: ReadableStream<Uint8Array>; exited: Promise<number> }
}

type ScriptStep = [string, string[]]

type ScriptResult = {
  ok: boolean
  script: string
  command: string
  stdout: string
  stderr: string
  exitCode: number
}

function resolveWorkspacePath(worktree: string, inputPath: string): string {
  if (!inputPath) {
    return worktree
  }
  if (inputPath.startsWith("/")) {
    return inputPath
  }

  const segments = worktree.replace(/\/+$/, "").split("/")
  for (const part of inputPath.split("/")) {
    if (!part || part === ".") {
      continue
    }
    if (part === "..") {
      if (segments.length > 1) {
        segments.pop()
      }
      continue
    }
    segments.push(part)
  }
  return segments.join("/") || "/"
}

async function runScript(script: string, args: string[], worktree: string): Promise<ScriptResult> {
  const scriptPath = `${worktree}/.opencode/skills/md-to-docx-pipeline/scripts/${script}`
  const py = "python3"
  const command = [py, scriptPath, ...args]
  const proc = BunRuntime.spawn(command, { cwd: worktree, stdout: "pipe", stderr: "pipe" })
  const [stdout, stderr, exitCode] = await Promise.all([
    new Response(proc.stdout).text(),
    new Response(proc.stderr).text(),
    proc.exited,
  ])
  return {
    ok: exitCode === 0,
    script,
    command: command.join(" "),
    stdout: stdout.trim(),
    stderr: stderr.trim(),
    exitCode,
  }
}

async function runSteps(steps: ScriptStep[], worktree: string): Promise<{ status: string; failed_step?: string; results: ScriptResult[] }> {
  const results: ScriptResult[] = []
  for (const [script, scriptArgs] of steps) {
    const result = await runScript(script, scriptArgs, worktree)
    results.push(result)
    if (!result.ok) {
      return { status: "failed", failed_step: script, results }
    }
  }
  return { status: "completed", results }
}

async function readJsonFile(path: string): Promise<any | undefined> {
  try {
    const text = await new Response((globalThis as any).Bun.file(path)).text()
    return JSON.parse(text)
  } catch {
    return undefined
  }
}

export const inspectTemplate = tool({
  // @ts-expect-error title is spec 2025-11-25, not yet in opencode plugin types
  title: "DOCX Template Inspector",
  description: `Read-only raw inspection of a DOCX template for LLM reasoning.

PRECONDITIONS:
- template_file must exist and be a valid .docx file.

POSTCONDITIONS:
- Writes: {run_dir}/template_inspection_raw.json (style hierarchy, anchors, fields).
- Returns: JSON with status + full inspection payload.

CALL ORDER:
- Must be called BEFORE validateExecutionOps and applyExecutionOps.
- Safe to call multiple times (idempotent); subsequent calls overwrite the JSON.

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
    required: ["ok", "inspection_file"],
  },
  args: {
    run_dir: tool.schema.string().describe("Run directory path under .office-auto/state/. Created automatically if not exists."),
    template_file: tool.schema.string().describe("Absolute or relative path to the .docx template file to inspect."),
  },
  async execute(args, context) {
    const absRunDir = resolveWorkspacePath(context.worktree, args.run_dir)
    const absTplFile = resolveWorkspacePath(context.worktree, args.template_file)
    const result = await runSteps(
      [["docx_inspect_raw.py", ["--template-file", absTplFile, "--run-dir", absRunDir]]],
      context.worktree,
    )
    const payload = await readJsonFile(`${absRunDir}/template_inspection_raw.json`)
    return JSON.stringify(
      {
        ...result,
        inspection_file: `${absRunDir}/template_inspection_raw.json`,
        inspection: payload,
      },
      null,
      2,
    )
  },
})

export const validateExecutionOps = tool({
  // @ts-expect-error title is spec 2025-11-25, not yet in opencode plugin types
  title: "DOCX Execution Ops Validator",
  description: `Validate LLM-generated execution_ops.json against raw template inspection to catch anchor mismatches, invalid paths, and structural conflicts.

PRECONDITIONS:
- {run_dir}/template_inspection_raw.json must exist (run inspectTemplate first).
- ops_file must exist and contain valid JSON with an "ops" array.

POSTCONDITIONS:
- Writes: {run_dir}/execution_ops_validation.json (warnings[], errors[], is_valid).
- Returns: JSON with validation status + detailed findings.

CALL ORDER:
- Must be called AFTER inspectTemplate and BEFORE applyExecutionOps.
- If warnings are present, LLM should fix execution_ops.json and re-validate before applying.

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
    run_dir: tool.schema.string().describe("Run directory under .office-auto/state/ where template_inspection_raw.json and execution_ops.json reside."),
    ops_file: tool.schema.string().describe("Absolute or relative path to the LLM-generated execution_ops.json file."),
    strict_mode: tool.schema.boolean().default(false).describe("If true, warnings are treated as errors and the tool returns status=failed. Use for final validation before production builds."),
  },
  async execute(args, context) {
    const absRunDir = resolveWorkspacePath(context.worktree, args.run_dir)
    const absOpsFile = resolveWorkspacePath(context.worktree, args.ops_file)
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

PRECONDITIONS:
- {run_dir}/execution_ops.json must exist and contain valid JSON with an "ops" array.
- template_file must exist and be a valid .docx file.
- For phases containing 'validate': {run_dir}/execution_ops_validation.json should exist (run validateExecutionOps first).

POSTCONDITIONS:
- Writes: {run_dir}/build_report.json, {run_dir}/post_process_report.json, and target_file (.docx).
- Returns: JSON with build status + build_report payload.

CALL ORDER:
- Must be called AFTER validateExecutionOps (recommended) and inspectTemplate.
- Use mode='incremental' to skip re-inspection if template_inspection_raw.json already exists.
- Use mode='ops_only' to skip inspect and run only compile→build→post_process.

ANNOTATIONS: writes output DOCX, non-idempotent (creates new artifacts each run).`,
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
    run_dir: tool.schema.string().describe("Run directory under .office-auto/state/ where execution_ops.json and template_inspection_raw.json reside."),
    template_file: tool.schema.string().describe("Absolute or relative path to the .docx template file."),
    ops_file: tool.schema.string().describe("Absolute or relative path to the LLM-generated execution_ops.json file."),
    target_file: tool.schema.string().describe("Absolute or relative path for the output .docx file."),
    source_file: tool.schema.string().default("").describe("Optional source markdown path, recorded in plan/run artifacts only."),
    mode: tool.schema
      .enum(["full", "incremental", "ops_only"])
      .default("full")
      .describe(
        "Build mode: " +
        "'full' runs inspect→compile→build→post_process (default); " +
        "'incremental' skips re-inspection if template_inspection_raw.json already exists in run_dir (faster for retry loops); " +
        "'ops_only' skips inspect and runs only compile→build→post_process (use when template is unchanged and only execution_ops.json was edited)."
      ),
  },
  async execute(args, context) {
    const absRunDir = resolveWorkspacePath(context.worktree, args.run_dir)
    const absTplFile = resolveWorkspacePath(context.worktree, args.template_file)
    const absOpsFile = resolveWorkspacePath(context.worktree, args.ops_file)
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
      steps.push(["docx_inspect_raw.py", ["--template-file", absTplFile, "--run-dir", absRunDir]])
    } else if (mode === "incremental") {
      // Incremental: skip re-inspect if template_inspection_raw.json already exists
      const inspectionPath = `${absRunDir}/template_inspection_raw.json`
      try {
        await new Response((globalThis as any).Bun.file(inspectionPath)).text()
        // File exists, skip inspect
      } catch {
        // File doesn't exist, fall back to full re-inspect
        steps.push(["docx_inspect_raw.py", ["--template-file", absTplFile, "--run-dir", absRunDir]])
      }
    }
    // ops_only: skip inspect entirely

    steps.push(["compile_execution_ops.py", compileArgs])
    steps.push(["build_docx.py", ["--run-dir", absRunDir]])
    steps.push(["post_process_docx.py", ["--run-dir", absRunDir]])

    const result = await runSteps(steps, context.worktree)
    const buildReport = await readJsonFile(`${absRunDir}/build_report.json`)
    return JSON.stringify(
      {
        ...result,
        mode: mode,
        build_report_file: `${absRunDir}/build_report.json`,
        build_report: buildReport,
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
  description: `Composite tool that runs one or more pipeline phases in sequence.

Phase order (always preserved): inspect → validate → apply → read.

Use this tool when:
- Running a full pipeline from scratch: phases=["all"]
- Resuming after LLM has written execution_ops.json: phases=["validate","apply","read"]
- Only verifying an existing output: phases=["read"]

Prefer individual tools (inspectTemplate, validateExecutionOps, etc.) when you need to inspect intermediate outputs or handle errors between phases.

PRECONDITIONS:
- For phases containing 'validate' or 'apply': {run_dir}/execution_ops.json must exist and contain valid JSON.
- For phase 'inspect': template_file must exist and be a valid .docx file.
- For phase 'read': {run_dir}/build_report.json must exist with status=completed.

POSTCONDITIONS:
- Writes: all intermediate artifacts for each phase run.
- Returns: aggregate result with per-phase status.

CALL ORDER:
- This tool replaces calling individual tools sequentially.
- Use phases=["all"] for full pipeline. Use custom arrays for partial runs.

ANNOTATIONS: writes output artifacts, non-idempotent, local filesystem only.`,
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
    const absOpsFile = resolveWorkspacePath(context.worktree, args.ops_file)
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
          [["docx_inspect_raw.py", ["--template-file", absTplFile, "--run-dir", absRunDir]]],
          context.worktree,
        )
        phasesStatus["inspect"] = { status: inspectResult.status, script: "docx_inspect_raw.py", exitCode: inspectResult.results[0]?.exitCode ?? 0 }
        if (inspectResult.status !== "completed") {
          overallStatus = "failed"
          failedPhase = "inspect"
          break
        }
        artifacts.inspection_file = `${absRunDir}/template_inspection_raw.json`
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
        const compileArgs = ["--run-dir", absRunDir, "--ops-file", absOpsFile, "--template-file", absTplFile, "--target-file", absTargetFile]
        if (absSourceFile) {
          compileArgs.push("--source-file", absSourceFile)
        }

        const applySteps: ScriptStep[] = []
        const mode = args.mode || "full"

        if (mode === "full") {
          applySteps.push(["docx_inspect_raw.py", ["--template-file", absTplFile, "--run-dir", absRunDir]])
        } else if (mode === "incremental") {
          const inspectionPath = `${absRunDir}/template_inspection_raw.json`
          try {
            await new Response((globalThis as any).Bun.file(inspectionPath)).text()
          } catch {
            applySteps.push(["docx_inspect_raw.py", ["--template-file", absTplFile, "--run-dir", absRunDir]])
          }
        }

        applySteps.push(["compile_execution_ops.py", compileArgs])
        applySteps.push(["build_docx.py", ["--run-dir", absRunDir]])
        applySteps.push(["post_process_docx.py", ["--run-dir", absRunDir]])

        const applyResult = await runSteps(applySteps, context.worktree)
        phasesStatus["apply"] = { status: applyResult.status, script: applyResult.failed_step || "compile_execution_ops.py", exitCode: applyResult.results[applyResult.results.length - 1]?.exitCode ?? 0 }
        if (applyResult.status !== "completed") {
          overallStatus = "failed"
          failedPhase = "apply"
          break
        }
        artifacts.build_report_file = `${absRunDir}/build_report.json`
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
