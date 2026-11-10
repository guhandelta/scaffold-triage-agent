import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { ArrowLeft } from 'lucide-react'
import type { ReactNode } from 'react'

import type { TicketRecord } from '@/client'
import { getTicketOptions, meOptions } from '@/client/@tanstack/react-query.gen'
import { DecisionBadge, StatusBadge } from '@/components/decision-badge'
import { ReviewPanel } from '@/components/review-panel'
import { SourceList } from '@/components/source-list'
import { formatTime, TicketHistory } from '@/components/ticket-history'
import { SuggestedReply, WhyPanel } from '@/components/triage-result'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { errorText } from '@/lib/tickets'

export function TicketDetailPage({ ticketId }: { ticketId: string }) {
  const ticket = useQuery(getTicketOptions({ path: { ticket_id: ticketId } }))
  const me = useQuery(meOptions())

  return (
    <div className="grid gap-6">
      <Link
        to="/tickets"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden /> All tickets
      </Link>
      {ticket.isPending ? (
        <p className="text-sm text-muted-foreground">Loading ticket…</p>
      ) : ticket.isError ? (
        <p className="text-sm text-destructive">
          {errorText(ticket.error, 'Could not load this ticket.')}
        </p>
      ) : (
        <TicketDetail
          record={ticket.data}
          review={
            me.data ? (
              <ReviewPanel
                key={ticket.data.history?.length ?? 0}
                record={ticket.data} permissions={me.data.permissions} role={me.data.role} />
            ) : (
              <p className="text-sm text-muted-foreground">
                {me.isError ? 'Could not check your permissions.' : 'Checking your permissions…'}
              </p>
            )
          }
        />
      )}
    </div>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card className="shadow-sm">
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-4">{children}</CardContent>
    </Card>
  )
}

export function TicketDetail({ record, review }: { record: TicketRecord; review: ReactNode }) {
  const { ticket, result, decision } = record
  const notes = record.notes ?? []

  return (
    <>
      <header className="grid gap-2">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold">{ticket.subject}</h1>
          <StatusBadge status={record.status} />
        </div>
        <p className="flex flex-wrap gap-x-3 text-sm text-muted-foreground">
          <span className="font-mono">#{record.ticket_id}</span>
          {ticket.customer_email && <span>{ticket.customer_email}</span>}
          <span>{record.owner ? `Owner: ${record.owner}` : 'No owner'}</span>
        </p>
      </header>

      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <div className="grid content-start gap-6">
          <Section title="Customer message">
            <p className="text-sm whitespace-pre-wrap">{ticket.body}</p>
          </Section>

          <Section title="Decision">
            <div className="flex flex-wrap items-center gap-2">
              <DecisionBadge action={decision.action} />
              {record.override ? (
                <Badge variant="outline">Changed by a reviewer</Badge>
              ) : (
                <span className="text-xs text-muted-foreground">
                  Routed {result.route} · decided by {result.provider}
                </span>
              )}
            </div>
            <WhyPanel reasoning={decision.reasoning} failedAttempts={result.failed_attempts} />
            {decision.action === 'reply' && decision.reply_text ? (
              <SuggestedReply text={decision.reply_text} title="Reply" />
            ) : (
              <p className="text-sm text-muted-foreground">No reply is sent. A person handles this ticket.</p>
            )}
            {record.override && (
              <details className="rounded-lg border p-3 text-sm">
                <summary className="cursor-pointer font-medium">The agent's original decision</summary>
                <div className="mt-3 grid gap-2">
                  <DecisionBadge action={result.decision.action} />
                  <p className="text-muted-foreground">{result.decision.reasoning}</p>
                  {result.decision.reply_text && (
                    <p className="whitespace-pre-wrap">{result.decision.reply_text}</p>
                  )}
                </div>
              </details>
            )}
          </Section>

          <Section title="Sources">
            <SourceList sources={result.sources ?? []} citations={result.decision.citations ?? []} />
          </Section>
        </div>

        <div className="grid content-start gap-6">
          <Section title="Review">{review}</Section>
          <Section title="Notes">
            {notes.length === 0 ? (
              <p className="text-sm text-muted-foreground">No notes yet.</p>
            ) : (
              <ul className="grid gap-3">
                {notes.map((note, index) => (
                  <li key={`${note.at}-${index}`} className="rounded-lg border p-3 text-sm">
                    <p className="whitespace-pre-wrap">{note.text}</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {note.author} · {formatTime(note.at)}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </Section>
          <Section title="History">
            <TicketHistory events={record.history ?? []} />
          </Section>
        </div>
      </div>
    </>
  )
}
