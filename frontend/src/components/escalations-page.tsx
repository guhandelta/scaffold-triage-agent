import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { assignMutation, escalationsOptions, escalationsQueryKey } from '@/client/@tanstack/react-query.gen'
import { EscalationsView } from '@/components/escalations-view'

export function EscalationsPage() {
  const queryClient = useQueryClient()
  const list = useQuery(escalationsOptions())
  const assign = useMutation(assignMutation())

  function onAssign(ticketId: string, owner: string) {
    assign.mutate(
      { path: { ticket_id: ticketId }, body: { owner } },
      {
        onSuccess: () => queryClient.invalidateQueries({ queryKey: escalationsQueryKey() }),
      },
    )
  }

  return (
    <div className="grid gap-6">
      <h1 className="text-lg font-semibold">Escalations</h1>
      <EscalationsView
        items={list.data}
        isPending={list.isPending}
        isError={list.isError}
        assigning={assign.isPending}
        assignFailed={assign.isError}
        onAssign={onAssign}
      />
    </div>
  )
}
