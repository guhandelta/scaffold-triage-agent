import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Sparkles } from 'lucide-react'
import { type FormEvent, useState } from 'react'

import { listTicketsQueryKey, triageMutation } from '@/client/@tanstack/react-query.gen'
import { TriageFlow, type FlowStatus } from '@/components/triage-flow'
import { TriageResultPanel } from '@/components/triage-result'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { SAMPLE_TICKETS, type SampleTicket } from '@/lib/samples'

export function TriagePage() {
  const queryClient = useQueryClient()
  const triage = useMutation(triageMutation())
  const [draft, setDraft] = useState<SampleTicket | null>(null)

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = new FormData(e.currentTarget)
    triage.mutate(
      {
        body: {
          subject: String(form.get('subject')),
          body: String(form.get('body')),
          customer_email: String(form.get('customer_email')) || null,
        },
      },
      {
        onSuccess: () => queryClient.invalidateQueries({ queryKey: listTicketsQueryKey() }),
      },
    )
  }

  const status: FlowStatus = triage.isPending
    ? 'running'
    : triage.isError
      ? 'error'
      : triage.data
        ? 'done'
        : 'idle'

  return (
    <div className="grid gap-6 lg:grid-cols-[1.1fr_1fr]">
      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="size-5 text-primary" aria-hidden /> New ticket
          </CardTitle>
          <CardDescription>The agent replies from the docs or hands the ticket to a person.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-5">
          <div className="flex flex-wrap gap-2" aria-label="Try a sample">
            {SAMPLE_TICKETS.map((sample) => (
              <Button
                key={sample.label}
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => setDraft(sample)}
              >
                {sample.label}
              </Button>
            ))}
          </div>
          <form key={draft?.subject ?? 'blank'} onSubmit={onSubmit} className="grid gap-4">
            <div className="grid gap-2">
              <Label htmlFor="customer_email">Customer email</Label>
              <Input id="customer_email" name="customer_email" type="email" placeholder="optional" />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="subject">Subject</Label>
              <Input id="subject" name="subject" required defaultValue={draft?.subject ?? ''} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="body">Message</Label>
              <Textarea id="body" name="body" rows={5} required defaultValue={draft?.body ?? ''} />
            </div>
            <Button type="submit" size="lg" disabled={triage.isPending}>
              {triage.isPending ? 'Deciding…' : 'Triage ticket'}
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle>Live triage</CardTitle>
          <CardDescription>Follow the ticket through the agent.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-6">
          <TriageFlow status={status} />
          {triage.isError && (
            <p className="text-sm text-destructive">Triage failed. Check that the API is running.</p>
          )}
          {triage.data && <TriageResultPanel result={triage.data} />}
        </CardContent>
      </Card>
    </div>
  )
}
