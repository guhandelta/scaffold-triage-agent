import { createFileRoute } from '@tanstack/react-router'

import { EscalationsPage } from '@/components/escalations-page'

export const Route = createFileRoute('/escalations')({
  component: EscalationsPage,
})
