import { useQuery } from '@tanstack/react-query'

import { listTicketsOptions } from '@/client/@tanstack/react-query.gen'
import { StatsBar } from '@/components/stats-bar'
import { TicketList } from '@/components/ticket-list'
import { summarize } from '@/lib/tickets'

export function TicketsPage() {
  const list = useQuery(listTicketsOptions())
  const records = list.data

  return (
    <div className="grid gap-6">
      <div>
        <h1 className="text-xl font-semibold">Tickets</h1>
        <p className="text-sm text-muted-foreground">Every ticket the agent has triaged, newest first.</p>
      </div>
      {records && <StatsBar stats={summarize(records)} />}
      <TicketList records={records} isPending={list.isPending} isError={list.isError} />
    </div>
  )
}
