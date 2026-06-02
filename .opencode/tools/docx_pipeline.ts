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

export const profileTemplate = tool({
  description: "Profile template and compile execution plan for DOCX pipeline",
  args: {
    run_dir: tool.schema.string().describe("Run directory under .office-auto/state"),
    template_file: tool.schema.string().describe("Template DOCX file path"),
    source_file: tool.schema.string().describe("Source markdown file path"),
    mode: tool.schema.string().default("preserve-template-scaffold"),
    target_file: tool.schema.string().describe("Target DOCX file path"),
  },
  async execute(args, context) {
    const steps: ScriptStep[] = [
      ["document_topology_detector.py", ["--template-file", args.template_file, "--run-dir", args.run_dir]],
      ["profile_template.py", ["--template-file", args.template_file, "--run-dir", args.run_dir]],
      ["template_suitability_report.py", ["--run-dir", args.run_dir]],
      ["generate_pandoc_style_map.py", ["--run-dir", args.run_dir]],
      ["input_processor.py", ["--source-file", args.source_file, "--run-dir", args.run_dir, "--style-spec-file", `${args.run_dir}/pandoc_style_spec.json`]],
      ["extract_sample_content.py", ["--sample-file", args.template_file, "--run-dir", args.run_dir, "--style-spec-file", `${args.run_dir}/pandoc_style_spec.json`]],
      ["parse_markdown.py", ["--source-file", `${args.run_dir}/normalized.md`, "--run-dir", args.run_dir]],
      ["plan_mapping.py", ["--mode", args.mode, "--run-dir", args.run_dir, "--source-file", args.source_file, "--template-file", args.template_file, "--target-file", args.target_file]],
      ["compile_execution_plan.py", ["--run-dir", args.run_dir]],
    ]

    const results: ScriptResult[] = []
    for (const [script, scriptArgs] of steps) {
      const result = await runScript(script, scriptArgs, context.worktree)
      results.push(result)
      if (!result.ok) {
        return JSON.stringify({ status: "failed", failed_step: script, results }, null, 2)
      }
    }
    return JSON.stringify({ status: "completed", results }, null, 2)
  },
})

export const buildDocx = tool({
  description: "Build DOCX from prepared execution plan",
  args: {
    run_dir: tool.schema.string().describe("Run directory under .office-auto/state"),
  },
  async execute(args, context) {
    const steps: ScriptStep[] = [
      ["build_docx.py", ["--run-dir", args.run_dir]],
      ["post_process_docx.py", ["--run-dir", args.run_dir]],
    ]

    const results: ScriptResult[] = []
    for (const [script, scriptArgs] of steps) {
      const result = await runScript(script, scriptArgs, context.worktree)
      results.push(result)
      if (!result.ok) {
        return JSON.stringify({ status: "failed", failed_step: script, results }, null, 2)
      }
    }
    return JSON.stringify({ status: "completed", results }, null, 2)
  },
})

export const qaDocx = tool({
  description: "Run roundtrip, QA and review layers for DOCX output",
  args: {
    run_dir: tool.schema.string().describe("Run directory under .office-auto/state"),
  },
  async execute(args, context) {
    const steps: ScriptStep[] = [
      ["roundtrip_pandoc.py", ["--run-dir", args.run_dir, "--style-spec-file", `${args.run_dir}/pandoc_style_spec.json`]],
      ["qa_docx.py", ["--run-dir", args.run_dir]],
      ["review_docx.py", ["--run-dir", args.run_dir]],
    ]

    const results: ScriptResult[] = []
    for (const [script, scriptArgs] of steps) {
      const result = await runScript(script, scriptArgs, context.worktree)
      results.push(result)
      if (!result.ok) {
        return JSON.stringify({ status: "failed", failed_step: script, results }, null, 2)
      }
    }
    return JSON.stringify({ status: "completed", results }, null, 2)
  },
})

export const runFullPipeline = tool({
  description: "Run the full DOCX wrapper pipeline via scripts/build_report.py",
  args: {
    run_dir: tool.schema.string().describe("Run directory under .office-auto/state"),
    source_file: tool.schema.string().describe("Source markdown file path"),
    template_file: tool.schema.string().describe("Template DOCX file path"),
    target_file: tool.schema.string().describe("Target DOCX file path"),
    mode: tool.schema.string().default("preserve-template-scaffold"),
  },
  async execute(args, context) {
    const py = "python3"
    const scriptPath = `${context.worktree}/scripts/build_report.py`
    const command = [
      py,
      scriptPath,
      "--run-dir",
      args.run_dir,
      "--source-file",
      args.source_file,
      "--template-file",
      args.template_file,
      "--target-file",
      args.target_file,
      "--mode",
      args.mode,
    ]

    const proc = BunRuntime.spawn(command, { cwd: context.worktree, stdout: "pipe", stderr: "pipe" })
    const [stdout, stderr, exitCode] = await Promise.all([
      new Response(proc.stdout).text(),
      new Response(proc.stderr).text(),
      proc.exited,
    ])

    return JSON.stringify(
      {
        status: exitCode === 0 ? "completed" : "failed",
        command: command.join(" "),
        stdout: stdout.trim(),
        stderr: stderr.trim(),
        exitCode,
      },
      null,
      2,
    )
  },
})
