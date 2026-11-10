import type { TicketRecord } from '@/client'
import { EscalationCard } from '@/components/escalation-card'

type Props = {
  items: TicketRecord[] | undefined
  isPending: boolean
  isError: boolean
  assigning: boolean
  assignFailed: boolean
  onAssign: (ticketId: string, owner: string) => void
}

export function EscalationsView({
  items,
  isPending,
  isError,
  assigning,
  assignFailed,
  onAssign,
}: Props) {
  if (isPending) return <p className="text-sm text-muted-foreground">Loading escalations…</p>
  if (isError) return <p className="text-sm text-destructive">Could not load escalations.</p>
  if (!items || items.length === 0) {
    return <p className="text-sm text-muted-foreground">Nothing needs a person right now.</p>
  }

  return (
    <div className="grid gap-6">
      {assignFailed && <p className="text-sm text-destructive">Could not assign that ticket.</p>}
      {items.map((record) => (
        <EscalationCard
          key={record.ticket_id}
          record={record}
          assigning={assigning}
          onAssign={(owner) => onAssign(record.ticket_id, owner)}
        />
      ))}
    </div>
  )
}
