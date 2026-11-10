import { Search } from 'lucide-react'
import { useState } from 'react'

import type { TicketRecord } from '@/client'
import { DecisionBadge } from '@/components/decision-badge'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { type DecisionFilter, filterTickets } from '@/lib/tickets'

const FILTERS: { value: DecisionFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'reply', label: 'Replied' },
  { value: 'escalate', label: 'Escalated' },
]

type Props = {
  records: TicketRecord[] | undefined
  isPending: boolean
  isError: boolean
}

export function TicketList({ records, isPending, isError }: Props) {
  const [decision, setDecision] = useState<DecisionFilter>('all')
  const [query, setQuery] = useState('')

  if (isPending) return <p className="text-sm text-muted-foreground">Loading tickets…</p>
  if (isError) return <p className="text-sm text-destructive">Could not load tickets.</p>
  if (!records || records.length === 0) {
    return (
      <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
        No tickets yet. Triage one from the home page and it will appear here.
      </div>
    )
  }

  const visible = filterTickets(records, { decision, query })

  return (
    <div className="grid gap-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div role="group" aria-label="Filter by decision" className="flex gap-2">
          {FILTERS.map((f) => (
            <button
              key={f.value}
              type="button"
              aria-pressed={decision === f.value}
              onClick={() => setDecision(f.value)}
              className={`rounded-full border px-3 py-1 text-sm transition ${
                decision === f.value ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
        <div className="relative sm:w-64">
          <Search className="pointer-events-none absolute top-2.5 left-3 size-4 text-muted-foreground" aria-hidden />
          <Input
            aria-label="Search tickets"
            placeholder="Search subject, owner, email"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="pl-9"
          />
        </div>
      </div>

      {visible.length === 0 ? (
        <p className="text-sm text-muted-foreground">No tickets match these filters.</p>
      ) : (
        <ul className="grid gap-3">
          {visible.map((record) => (
            <li key={record.ticket_id} className="rounded-xl border bg-card p-4 shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-medium">{record.ticket.subject}</p>
                <DecisionBadge action={record.result.decision.action} />
              </div>
              <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{record.ticket.body}</p>
              <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
                <Badge variant="outline">Decided by {record.result.provider}</Badge>
                <Badge variant="outline">{record.owner ? `Owner: ${record.owner}` : 'No owner'}</Badge>
                <span className="self-center font-mono">#{record.ticket_id}</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
