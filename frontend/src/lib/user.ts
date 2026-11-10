import type { Role } from '@/client'
import { client } from '@/client/client.gen'

/** Who the app acts as. There is no sign-in yet, so the API trusts these two headers. */
export type Viewer = { name: string; role: Role }

export const ROLES: { value: Role; label: string }[] = [
  { value: 'viewer', label: 'Viewer' },
  { value: 'agent', label: 'Support agent' },
  { value: 'reviewer', label: 'Reviewer' },
  { value: 'admin', label: 'Admin' },
]

export const DEFAULT_VIEWER: Viewer = { name: 'Reviewer', role: 'reviewer' }
const KEY = 'triage.viewer'

/** Header values must be plain ASCII, so other characters are dropped. */
export function cleanName(name: string): string {
  return name.replace(/[^\x20-\x7E]/g, '').trim().slice(0, 80)
}

export function loadViewer(): Viewer {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) ?? 'null') as Partial<Viewer> | null
    const role = ROLES.find((r) => r.value === saved?.role)?.value
    const name = cleanName(String(saved?.name ?? ''))
    if (role && name) return { name, role }
  } catch {
    // Unreadable storage falls back to the default.
  }
  return DEFAULT_VIEWER
}

export function saveViewer(viewer: Viewer): Viewer {
  const clean = { name: cleanName(viewer.name) || DEFAULT_VIEWER.name, role: viewer.role }
  try {
    localStorage.setItem(KEY, JSON.stringify(clean))
  } catch {
    // Storage can be blocked; the choice then lasts until the page reloads.
  }
  return clean
}

let installed = false

/** Send the current viewer with every API request. Safe to call more than once. */
export function installViewerHeaders() {
  if (installed) return
  installed = true
  client.interceptors.request.use((request) => {
    const viewer = loadViewer()
    request.headers.set('X-User-Name', viewer.name)
    request.headers.set('X-User-Role', viewer.role)
    return request
  })
}
