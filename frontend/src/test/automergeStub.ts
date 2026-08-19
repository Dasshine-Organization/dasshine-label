/** E2E / 无 Wasm 环境下的 Automerge 替身（不连真共编）。 */

export type Doc<T> = T

export function from<T>(initial: T): Doc<T> {
  return structuredClone(initial)
}

export function load<T>(_data: Uint8Array): Doc<T> {
  return from({} as T)
}

export function save(_doc: Doc<unknown>): Uint8Array {
  return new Uint8Array()
}

export function getChanges(_before: Doc<unknown>, _after: Doc<unknown>): Uint8Array[] {
  return []
}

export function getLastLocalChange(_doc: Doc<unknown>): Uint8Array | null {
  return null
}

export function change<T>(doc: Doc<T>, fn: (d: T) => void): Doc<T> {
  const next = structuredClone(doc)
  fn(next)
  return next
}

export function applyChanges<T>(doc: Doc<T>, _changes: Uint8Array[]): [Doc<T>] {
  return [doc]
}
