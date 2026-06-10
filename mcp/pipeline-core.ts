import { spawn as nodeSpawn } from "node:child_process"
import { access as nodeAccess, mkdir as nodeMkdir, readFile as nodeReadFile, writeFile as nodeWriteFile } from "node:fs/promises"

type BunLike = {
  spawn: (
    command: string[],
    opts: { cwd: string; stdout: "pipe"; stderr: "pipe" },
  ) => { stdout: ReadableStream<Uint8Array>; stderr: ReadableStream<Uint8Array>; exited: Promise<number> }
  file: (path: string) => { text: () => Promise<string> }
  write: (path: string, data: string) => Promise<void>
}

const BunRuntime = (globalThis as any).Bun as BunLike | undefined

let _pythonPath: string | null = null
const PYTHON_CANDIDATES = ["python3", "python", "/usr/bin/python3", "/usr/bin/python"]

async function findPython(): Promise<string> {
  if (_pythonPath) return _pythonPath
  const tried: string[] = []
  for (const candidate of PYTHON_CANDIDATES) {
    tried.push(candidate)
    try {
      let ok = false
      if (BunRuntime) {
        const proc = BunRuntime.spawn([candidate, "--version"], { cwd: "/", stdout: "pipe", stderr: "pipe" })
        const code = await proc.exited
        ok = code === 0
      } else {
        const code = await new Promise<number>((resolve) => {
          const p = nodeSpawn(candidate, ["--version"])
          p.on("close", (c) => resolve(c ?? 1))
          p.on("error", () => resolve(1))
        })
        ok = code === 0
      }
      if (ok) {
        _pythonPath = candidate
        return candidate
      }
    } catch {
      // try next candidate
    }
  }
  throw new Error(`Python not found. Tried: ${tried.join(", ")}. Install python3 or add to PATH.`)
}

export type ScriptStep = [string, string[]]

export type ScriptResult = {
  ok: boolean
  script: string
  command: string
  stdout: string
  stderr: string
  exitCode: number
}

export function resolveWorkspacePath(worktree: string, inputPath: string): string {
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

export function makeAutoRunDir(worktree: string, suffix = "auto"): string {
  const ts = new Date().toISOString().replace(/[-:T]/g, "").slice(0, 15)
  return `${worktree.replace(/\/+$/, "")}/.office-auto/state/${ts}_${suffix}`
}

export function resolveRunDir(worktree: string, inputPath: string): string {
  if (!inputPath || inputPath.includes("$(")) {
    return makeAutoRunDir(worktree, "auto")
  }
  return resolveWorkspacePath(worktree, inputPath)
}

/** @deprecated Use resolveRunDir instead */
export const resolveInspectionRunDir = resolveRunDir

export function resolveRunDirArtifact(runDir: string, inputPath: string, fallbackFile: string): string {
  if (inputPath) {
    return inputPath
  }
  return `${runDir.replace(/\/+$/, "")}/${fallbackFile}`
}

export function parseMarkdownHeadings(markdownText: string): Array<{ level: number; text: string }> {
  return markdownText
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.startsWith("#"))
    .map((line) => {
      const match = line.match(/^(#+)\s+(.*)$/)
      if (!match) {
        return null
      }
      return { level: match[1].length, text: match[2].trim() }
    })
    .filter((value): value is { level: number; text: string } => Boolean(value))
}

export async function runScript(script: string, args: string[], worktree: string): Promise<ScriptResult> {
  const python = await findPython()
  const scriptPath = `${worktree}/.opencode/skills/md-to-docx-pipeline/scripts/${script}`
  const command = [python, scriptPath, ...args]
  let stdout = ""
  let stderr = ""
  let exitCode = 0

  if (BunRuntime) {
    const proc = BunRuntime.spawn(command, { cwd: worktree, stdout: "pipe", stderr: "pipe" })
    const result = await Promise.all([
      new Response(proc.stdout).text(),
      new Response(proc.stderr).text(),
      proc.exited,
    ])
    stdout = result[0]
    stderr = result[1]
    exitCode = result[2]
  } else {
    const proc = nodeSpawn(command[0], command.slice(1), { cwd: worktree })
    const stdoutChunks: Buffer[] = []
    const stderrChunks: Buffer[] = []
    proc.stdout?.on("data", (chunk) => stdoutChunks.push(Buffer.from(chunk)))
    proc.stderr?.on("data", (chunk) => stderrChunks.push(Buffer.from(chunk)))
    exitCode = await new Promise<number>((resolve, reject) => {
      proc.on("error", reject)
      proc.on("close", (code) => resolve(code ?? 0))
    })
    stdout = Buffer.concat(stdoutChunks).toString("utf8")
    stderr = Buffer.concat(stderrChunks).toString("utf8")
  }

  return {
    ok: exitCode === 0,
    script,
    command: command.join(" "),
    stdout: stdout.trim(),
    stderr: stderr.trim(),
    exitCode,
  }
}

export async function runSteps(
  steps: ScriptStep[],
  worktree: string,
): Promise<{ status: string; failed_step?: string; results: ScriptResult[] }> {
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

export async function readJsonFile(path: string): Promise<any | undefined> {
  try {
    const text = await readTextFile(path)
    return JSON.parse(text)
  } catch {
    return undefined
  }
}

export async function readTextFile(path: string): Promise<string> {
  if (BunRuntime) {
    return BunRuntime.file(path).text()
  }
  return nodeReadFile(path, "utf8")
}

export async function fileExists(path: string): Promise<boolean> {
  try {
    if (BunRuntime) {
      await BunRuntime.file(path).text()
      return true
    }
    await nodeAccess(path)
    return true
  } catch {
    return false
  }
}

export async function writeJsonFile(path: string, payload: unknown): Promise<void> {
  const text = JSON.stringify(payload, null, 2) + "\n"
  if (BunRuntime) {
    await BunRuntime.write(path, text)
    return
  }
  await nodeMkdir(path.split("/").slice(0, -1).join("/") || "/", { recursive: true })
  await nodeWriteFile(path, text, "utf8")
}

// === New utilities ===

export type SpawnResult = {
  exit_code: number
  stdout: string
  stderr: string
  stdout_json?: any
}

export async function spawnPython(
  script: string,
  args: string[],
  options?: { timeout?: number; cwd?: string },
): Promise<SpawnResult> {
  const python = await findPython()
  const scriptPath = `${options?.cwd || "/"}/.opencode/skills/md-to-docx-pipeline/scripts/${script}`
  const command = [python, scriptPath, ...args]
  const cwd = options?.cwd || process.cwd()
  let stdout = ""
  let stderr = ""
  let exitCode = 0

  if (BunRuntime) {
    const proc = BunRuntime.spawn(command, { cwd, stdout: "pipe", stderr: "pipe" })
    const exitedPromise = proc.exited
    if (options?.timeout) {
      const timer = new Promise<number>((_, reject) =>
        setTimeout(() => reject(new Error(`spawnPython timeout after ${options.timeout}ms`)), options.timeout),
      )
      exitCode = await Promise.race([exitedPromise, timer])
    } else {
      exitCode = await exitedPromise
    }
    ;[stdout, stderr] = await Promise.all([
      new Response(proc.stdout).text(),
      new Response(proc.stderr).text(),
    ])
  } else {
    const proc = nodeSpawn(command[0], command.slice(1), { cwd })
    const stdoutChunks: Buffer[] = []
    const stderrChunks: Buffer[] = []
    proc.stdout?.on("data", (chunk) => stdoutChunks.push(Buffer.from(chunk)))
    proc.stderr?.on("data", (chunk) => stderrChunks.push(Buffer.from(chunk)))
    exitCode = await new Promise<number>((resolve, reject) => {
      proc.on("error", reject)
      proc.on("close", (code) => resolve(code ?? 0))
    })
    stdout = Buffer.concat(stdoutChunks).toString("utf8")
    stderr = Buffer.concat(stderrChunks).toString("utf8")
  }

  const result: SpawnResult = {
    exit_code: exitCode,
    stdout: stdout.trim(),
    stderr: stderr.trim(),
  }
  try {
    result.stdout_json = JSON.parse(result.stdout)
  } catch {
    // stdout is not JSON, that's fine
  }
  return result
}

export async function mergeJsonFile(path: string, data: Record<string, unknown>): Promise<void> {
  const existing = await readJsonFile(path)
  const merged = { ...(existing || {}), ...data }
  await writeJsonFile(path, merged)
}

export function safeResolvePath(candidates: (string | null | undefined)[]): string | null {
  for (const c of candidates) {
    if (c && c.trim() && c.trim() !== "null" && c.trim() !== "None") {
      return c.trim()
    }
  }
  return null
}

export async function createRunDir(worktree: string, templateFile: string): Promise<string> {
  const ts = new Date().toISOString().replace(/[-:T]/g, "").slice(0, 15)
  const templateName = templateFile
    .split("/").pop()!
    .replace(/\.docx$/, "")
    .replace(/[^a-zA-Z0-9_-]/g, "_")
    .slice(0, 40)
  const runDir = `${worktree.replace(/\/+$/, "")}/.office-auto/state/${ts}_${templateName}`
  if (BunRuntime) {
    await BunRuntime.write(`${runDir}/.gitkeep`, "")
  } else {
    await nodeMkdir(runDir, { recursive: true })
  }
  return runDir
}

export function jsonToolResult(output: Record<string, unknown>) {
  return {
    content: [{ type: "text" as const, text: JSON.stringify(output, null, 2) }],
    structuredContent: output,
  }
}
