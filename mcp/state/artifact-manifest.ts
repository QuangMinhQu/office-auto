import { createHash } from "node:crypto"
import { readFile as nodeReadFile, stat as nodeStat, writeFile as nodeWriteFile, mkdir as nodeMkdir } from "node:fs/promises"
import type { ArtifactRef, PipelinePhase } from "./pipeline-state"
import { readJsonFile, writeJsonFile } from "../pipeline-core"

type BunLike = {
  file: (path: string) => { text: () => Promise<string>; arrayBuffer: () => Promise<ArrayBuffer> }
  write: (path: string, data: string) => Promise<void>
}

const BunRuntime = (globalThis as any).Bun as BunLike | undefined

const MANIFEST_FILE = "artifacts.json"

export interface ArtifactManifest {
  run_id: string
  updated_at: string
  entries: Record<string, ArtifactRef>
}

export async function computeSha256(filePath: string): Promise<string> {
  if (BunRuntime) {
    const buf = await BunRuntime.file(filePath).arrayBuffer()
    return createHash("sha256").update(Buffer.from(buf)).digest("hex")
  }
  const buf = await nodeReadFile(filePath)
  return createHash("sha256").update(buf).digest("hex")
}

export async function fileExists(path: string): Promise<boolean> {
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

export async function registerArtifact(
  runDir: string,
  params: {
    name: string
    path: string
    schema?: string
    created_by?: string
    phase?: PipelinePhase
  },
): Promise<ArtifactRef> {
  const exists = await fileExists(params.path)
  if (!exists) {
    throw new Error(`Artifact file does not exist: ${params.path}`)
  }

  const sha256 = await computeSha256(params.path)

  const ref: ArtifactRef = {
    path: params.path,
    sha256,
    schema: params.schema,
    created_by: params.created_by,
    phase: params.phase,
    valid: true,
  }

  const manifest = await loadManifest(runDir)
  manifest.entries[params.name] = ref
  manifest.updated_at = new Date().toISOString()
  await saveManifest(runDir, manifest)

  return ref
}

export async function verifyArtifact(
  runDir: string,
  name: string,
): Promise<{ valid: boolean; reason?: string }> {
  const manifest = await loadManifest(runDir)
  const entry = manifest.entries[name]

  if (!entry) {
    return { valid: false, reason: `Artifact '${name}' not found in manifest` }
  }

  const exists = await fileExists(entry.path)
  if (!exists) {
    return { valid: false, reason: `Artifact file missing: ${entry.path}` }
  }

  const currentHash = await computeSha256(entry.path)
  if (currentHash !== entry.sha256) {
    return { valid: false, reason: `Checksum mismatch for '${name}': expected ${entry.sha256}, got ${currentHash}` }
  }

  return { valid: true }
}

export async function verifyAllArtifacts(
  runDir: string,
  requiredNames?: string[],
): Promise<{ allValid: boolean; results: Record<string, { valid: boolean; reason?: string }> }> {
  const manifest = await loadManifest(runDir)
  const names = requiredNames || Object.keys(manifest.entries)
  const results: Record<string, { valid: boolean; reason?: string }> = {}
  let allValid = true

  for (const name of names) {
    const result = await verifyArtifact(runDir, name)
    results[name] = result
    if (!result.valid) allValid = false
  }

  return { allValid, results }
}

export async function loadManifest(runDir: string): Promise<ArtifactManifest> {
  const data = await readJsonFile(`${runDir}/${MANIFEST_FILE}`)
  if (data) return data as ArtifactManifest
  return {
    run_id: runDir.split("/").pop() || "unknown",
    updated_at: new Date().toISOString(),
    entries: {},
  }
}

export async function saveManifest(runDir: string, manifest: ArtifactManifest): Promise<void> {
  await writeJsonFile(`${runDir}/${MANIFEST_FILE}`, manifest)
}

export async function atomicWrite(filePath: string, content: string): Promise<void> {
  const tmpPath = `${filePath}.tmp.${Date.now()}`
  if (BunRuntime) {
    await BunRuntime.write(tmpPath, content)
  } else {
    await nodeMkdir(filePath.split("/").slice(0, -1).join("/") || "/", { recursive: true })
    await nodeWriteFile(tmpPath, content, "utf8")
  }

  if (BunRuntime) {
    // Bun: write directly since rename may not be available
    await BunRuntime.write(filePath, content)
  } else {
    const nodeFs = await import("node:fs/promises")
    await nodeFs.rename(tmpPath, filePath)
  }
}
