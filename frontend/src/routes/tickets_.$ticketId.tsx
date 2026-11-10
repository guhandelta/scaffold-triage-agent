import { createFileRoute } from '@tanstack/react-router'

import { TicketDetailPage } from '@/components/ticket-detail-page'

export const Route = createFileRoute('/tickets_/$ticketId')({
  component: TicketRoute,
})

function TicketRoute() {
  const { ticketId } = Route.useParams()
  return <TicketDetailPage ticketId={ticketId} />
}
