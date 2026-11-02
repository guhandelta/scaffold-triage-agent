import { useMutation } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
import type { FormEvent } from 'react'

import { triageMutation } from '@/client/@tanstack/react-query.gen'
import type { TriageResult } from '@/client'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'

export const Route = createFileRoute('/')({
  component: TriagePage,
})

function TriagePage() {
  const triage = useMutation(triageMutation())

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = new FormData(e.currentTarget)
    triage.mutate({
      body: {
        subject: String(form.get('subject')),
        body: String(form.get('body')),
        customer_email: String(form.get('customer_email')) || null,
      },
    })
  }

  return (
    <div className="grid gap-6">
      <Card>
        <CardHeader>
          <CardTitle>New ticket</CardTitle>
          <CardDescription>The agent decides to reply or escalate to a person.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="grid gap-4">
            <div className="grid gap-2">
              <Label htmlFor="customer_email">Customer email</Label>
              <Input id="customer_email" name="customer_email" type="email" placeholder="optional" />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="subject">Subject</Label>
              <Input id="subject" name="subject" required />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="body">Message</Label>
              <Textarea id="body" name="body" rows={5} required />
            </div>
            <Button type="submit" disabled={triage.isPending}>
              {triage.isPending ? 'Deciding…' : 'Triage'}
            </Button>
          </form>
        </CardContent>
      </Card>

      {triage.isError && <p className="text-sm text-destructive">Triage failed.</p>}
      {triage.data && <Result result={triage.data} />}
    </div>
  )
}

function Result({ result }: { result: TriageResult }) {
  const { decision } = result
  return (
    <Card>
      <CardHeader>
        <CardTitle>{decision.action === 'escalate' ? 'Escalate to a person' : 'Reply'}</CardTitle>
        <CardDescription>{decision.reasoning}</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        {decision.reply_text && (
          <p className="whitespace-pre-wrap rounded-md bg-muted p-3">{decision.reply_text}</p>
        )}
        <p className="text-xs text-muted-foreground">
          Route: {result.route} · Decided by: {result.provider}
        </p>
        {result.failed_attempts.length > 0 && (
          <div className="text-xs text-muted-foreground">
            <p>Tried before that:</p>
            <ul className="list-disc pl-5">
              {result.failed_attempts.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
