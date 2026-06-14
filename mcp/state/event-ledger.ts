import { readFile as nodeReadFile, appendFile as nodeAppendFile, writeFile as nodeWriteFile, mkdir as nodeMkdir } from "node:fs/promises"
import type { PipelineEvent } from "./events"

type BunLike = {
  file: (path: string) => { text: () => Promise<string> }
  write: (path: string, data: string) => Promise<void>
}

const BunRuntime = (globalThis as any).Bun as BunLike | undefined

const EVENT_FILE = "events.jsonl"

async function readText(path: string): Promise<string> {
  if (BunRuntime) return BunRuntime.file(path).text()
  return nodeReadFile(path, "utf8")
}

async function writeText(path: string, data: string): Promise<void> {
  if (BunRuntime) {
    await BunRuntime.write(path, data)
    return
  }
  await nodeMkdir(path.split("/").slice(0, -1).join("/") || "/", { recursive: true })
  await nodeWriteFile(path, data, "utf8")
}

async function appendText(path: string, data: string): Promise<void> {
  if (BunRuntime) {
    const existing = await readText(path).catch(() => "")
    await BunRuntime.write(path, existing + data)
    return
  }
  await nodeMkdir(path.split("/").slice(0, -1).join("/") || "/", { recursive: true })
  await nodeAppendFile(path, data, "utf8")
}

export async function appendEvent(runDir: string, event: PipelineEvent): Promise<void> {
  const line = JSON.stringify(event) + "\n"
  const path = `${runDir}/${EVENT_FILE}`
  await appendText(path, line)
}

export async function loadEvents(runDir: string): Promise<PipelineEvent[]> {
  const path = `${runDir}/${EVENT_FILE}`
  try {
    const text = await readText(path)
    if (!text.trim()) return []
    return text
      .split("\n")
      .filter((line) => line.trim())
      .map((line) => JSON.parse(line) as PipelineEvent)
  } catch {
    return []
  }
}

export async function appendEvents(runDir: string, events: PipelineEvent[]): Promise<void> {
  const lines = events.map((e) => JSON.stringify(e) + "\n").join("")
  const path = `${runDir}/${EVENT_FILE}`
  await appendText(path, lines)
}

export async function clearEvents(runDir: string): Promise<void> {
  const path = `${runDir}/${EVENT_FILE}`
  await writeText(path, "")
}
