import type { Action, TicketStatus } from '@/client'
import { Badge } from '@/components/ui/badge'

export function DecisionBadge({ action }: { action: Action }) {
  if (action === 'escalate') {
    return <Badge className="bg-amber-100 text-amber-900 hover:bg-amber-100 dark:bg-amber-400/15 dark:text-amber-200">Escalated</Badge>
  }
  return <Badge className="bg-emerald-100 text-emerald-900 hover:bg-emerald-100 dark:bg-emerald-400/15 dark:text-emerald-200">Replied</Badge>
}

/** Where the ticket stands now, which can differ from the agent's first decision. */
export function StatusBadge({ status }: { status: TicketStatus }) {
  if (status === 'resolved') {
    return <Badge className="bg-sky-100 text-sky-900 hover:bg-sky-100 dark:bg-sky-400/15 dark:text-sky-200">Resolved</Badge>
  }
  return <DecisionBadge action={status === 'escalated' ? 'escalate' : 'reply'} />
}
