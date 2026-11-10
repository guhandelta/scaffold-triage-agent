import { useQueryClient } from '@tanstack/react-query'
import { UserRound } from 'lucide-react'
import { useState } from 'react'

import type { Role } from '@/client'
import { loadViewer, ROLES, saveViewer } from '@/lib/user'

/**
 * Pick who the app acts as. A stand-in for sign-in: the API reads the name and role from
 * request headers, so switching here changes what the review panel allows.
 */
export function ViewerSwitcher() {
  const queryClient = useQueryClient()
  const [viewer, setViewer] = useState(loadViewer)
  const [name, setName] = useState(viewer.name)

  function apply(next: { name: string; role: Role }) {
    const saved = saveViewer(next)
    setViewer(saved)
    setName(saved.name)
    queryClient.invalidateQueries()
  }

  return (
    <div className="flex items-center gap-2 text-sm">
      <UserRound className="size-4 text-muted-foreground" aria-hidden />
      <input
        aria-label="Your name"
        value={name}
        maxLength={80}
        onChange={(e) => setName(e.target.value)}
        onBlur={() => name !== viewer.name && apply({ ...viewer, name })}
        onKeyDown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
        className="w-24 rounded-md border bg-background px-2 py-1"
      />
      <select
        aria-label="Your role"
        value={viewer.role}
        onChange={(e) => apply({ ...viewer, role: e.target.value as Role })}
        className="rounded-md border bg-background px-2 py-1"
      >
        {ROLES.map((r) => (
          <option key={r.value} value={r.value}>
            {r.label}
          </option>
        ))}
      </select>
    </div>
  )
}
