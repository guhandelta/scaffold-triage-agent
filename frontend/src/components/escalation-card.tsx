import { Link } from '@tanstack/react-router'
import { type FormEvent, useState } from 'react'

import type { TicketRecord } from '@/client'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

type Props = {
  record: TicketRecord
  assigning: boolean
  onAssign: (owner: string) => void
}

export function EscalationCard({ record, assigning, onAssign }: Props) {
  const [owner, setOwner] = useState('')
  const { ticket, result } = record

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const name = owner.trim()
    if (name) onAssign(name)
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between gap-2">
          <Link
            to="/tickets/$ticketId"
            params={{ ticketId: record.ticket_id }}
            className="hover:underline"
          >
            {ticket.subject}
          </Link>
          {record.owner ? (
            <Badge variant="secondary">Owner: {record.owner}</Badge>
          ) : (
            <Badge variant="outline">Unassigned</Badge>
          )}
        </CardTitle>
        <CardDescription>{record.decision.reasoning}</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <p className="whitespace-pre-wrap text-sm">{ticket.body}</p>
        <p className="text-xs text-muted-foreground">
          {ticket.customer_email ? `${ticket.customer_email} · ` : ''}
          Route: {result.route} · Decided by: {result.provider}
        </p>
        <form onSubmit={onSubmit} className="flex items-end gap-2">
          <div className="grid flex-1 gap-2">
            <Label htmlFor={`owner-${record.ticket_id}`}>Owner</Label>
            <Input
              id={`owner-${record.ticket_id}`}
              value={owner}
              onChange={(e) => setOwner(e.target.value)}
              placeholder="Name of the person handling it"
              maxLength={80}
            />
          </div>
          <Button type="submit" disabled={assigning || owner.trim() === ''}>
            {assigning ? 'Assigning…' : 'Assign'}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}
