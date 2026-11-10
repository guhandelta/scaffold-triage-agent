import { createFileRoute } from '@tanstack/react-router'

import { TicketsPage } from '@/components/tickets-page'

export const Route = createFileRoute('/tickets')({
  component: TicketsPage,
})
