/** E2E 无 Wasm 时的 Automerge 替身：本地改文档、不发 CRDT。仅 VITE_E2E_STUB_AUTOMERGE 时 alias 进来。 */

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
