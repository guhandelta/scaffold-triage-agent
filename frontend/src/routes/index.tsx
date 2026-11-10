import { createFileRoute } from '@tanstack/react-router'

import { TriagePage } from '@/components/triage-page'

export const Route = createFileRoute('/')({
  component: TriagePage,
})
