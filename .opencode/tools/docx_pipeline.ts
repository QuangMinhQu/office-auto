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
  description: "Read-only raw template inspection for LLM reasoning",
  args: {
    run_dir: tool.schema.string().describe("Run directory under .office-auto/state"),
    template_file: tool.schema.string().describe("Template DOCX file path"),
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
  description: "Validate LLM-generated execution_ops.json against raw template inspection",
  args: {
    run_dir: tool.schema.string().describe("Run directory under .office-auto/state"),
    ops_file: tool.schema.string().describe("LLM-generated execution_ops.json path"),
  },
  async execute(args, context) {
    const absRunDir = resolveWorkspacePath(context.worktree, args.run_dir)
    const absOpsFile = resolveWorkspacePath(context.worktree, args.ops_file)
    const result = await runSteps(
      [["docx_validate_ops.py", ["--run-dir", absRunDir, "--ops-file", absOpsFile]]],
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
  description: "Mechanical apply of execution_ops.json to a DOCX template",
  args: {
    run_dir: tool.schema.string().describe("Run directory under .office-auto/state"),
    template_file: tool.schema.string().describe("Template DOCX file path"),
    ops_file: tool.schema.string().describe("LLM-generated execution_ops.json path"),
    target_file: tool.schema.string().describe("Target DOCX file path"),
    source_file: tool.schema.string().default("").describe("Optional source markdown path recorded in plan/run artifacts only"),
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
    const steps: ScriptStep[] = [
      ["docx_inspect_raw.py", ["--template-file", absTplFile, "--run-dir", absRunDir]],
      ["compile_execution_ops.py", compileArgs],
      ["build_docx.py", ["--run-dir", absRunDir]],
      ["post_process_docx.py", ["--run-dir", absRunDir]],
    ]
    const result = await runSteps(steps, context.worktree)
    const buildReport = await readJsonFile(`${absRunDir}/build_report.json`)
    return JSON.stringify(
      {
        ...result,
        build_report_file: `${absRunDir}/build_report.json`,
        build_report: buildReport,
      },
      null,
      2,
    )
  },
})

export const readResult = tool({
  description: "Read a built DOCX back into text/structure summaries for LLM verification",
  args: {
    run_dir: tool.schema.string().describe("Run directory under .office-auto/state"),
    target_file: tool.schema.string().default("").describe("Optional target DOCX file path override"),
  },
  async execute(args, context) {
    const absRunDir = resolveWorkspacePath(context.worktree, args.run_dir)
    const steps: ScriptStep[] = [["docx_read_result.py", ["--run-dir", absRunDir]]]
    if (args.target_file) {
      steps[0][1].push("--file", resolveWorkspacePath(context.worktree, args.target_file))
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
