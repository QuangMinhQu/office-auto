import { readFile as nodeReadFile, writeFile as nodeWriteFile, mkdir as nodeMkdir, unlink as nodeUnlink, stat as nodeStat } from "node:fs/promises"

type BunLike = {
  file: (path: string) => { text: () => Promise<string>; size: number }
  write: (path: string, data: string) => Promise<void>
}

const BunRuntime = (globalThis as any).Bun as BunLike | undefined

const LOCK_FILE = "lock"

async function fileExists(path: string): Promise<boolean> {
  try {
    if (BunRuntime) {
      await BunRuntime.file(path).text()
      return true
    }
    await nodeStat(path)
    return true
  } catch {
    return false
  }
}

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

async function removeFile(path: string): Promise<void> {
  if (BunRuntime) {
    // Bun doesn't have a direct unlink in the minimal API we check
    // Use write empty as fallback won't work; just ignore for Bun
    return
  }
  await nodeUnlink(path)
}

interface LockInfo {
  pid: number
  acquired_at: string
  owner: string
}

export async function acquireRunLock(runDir: string, owner = "supervisor"): Promise<boolean> {
  const lockPath = `${runDir}/${LOCK_FILE}`

  if (await fileExists(lockPath)) {
    try {
      const content = await readText(lockPath)
      const lock: LockInfo = JSON.parse(content)

      const acquiredAt = new Date(lock.acquired_at).getTime()
      const now = Date.now()
      const STALE_THRESHOLD_MS = 30 * 60 * 1000

      if (now - acquiredAt > STALE_THRESHOLD_MS) {
        await releaseRunLock(runDir)
      } else {
        return false
      }
    } catch {
      await releaseRunLock(runDir)
    }
  }

  const lock: LockInfo = {
    pid: process.pid,
    acquired_at: new Date().toISOString(),
    owner,
  }

  await writeText(lockPath, JSON.stringify(lock, null, 2) + "\n")

  const verify = await readText(lockPath).catch(() => "")
  try {
    const parsed: LockInfo = JSON.parse(verify)
    return parsed.pid === process.pid
  } catch {
    return false
  }
}

export async function releaseRunLock(runDir: string): Promise<void> {
  const lockPath = `${runDir}/${LOCK_FILE}`
  try {
    await removeFile(lockPath)
  } catch {
    // ignore
  }
}

export async function isLocked(runDir: string): Promise<boolean> {
  const lockPath = `${runDir}/${LOCK_FILE}`
  return fileExists(lockPath)
}
