import { Link } from '@tanstack/react-router'
import { ArrowRight, Check, Copy, Lightbulb } from 'lucide-react'
import { useState } from 'react'

import type { TriageResult } from '@/client'
import { DecisionBadge } from '@/components/decision-badge'
import { SourceList } from '@/components/source-list'
import { Button } from '@/components/ui/button'

export function TriageResultPanel({ result }: { result: TriageResult }) {
  const { decision } = result

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <DecisionBadge action={decision.action} />
          <span className="text-xs text-muted-foreground">
            Routed {result.route} · decided by {result.provider}
          </span>
        </div>
        <Link
          to="/tickets/$ticketId"
          params={{ ticketId: result.ticket_id }}
          className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
        >
          Open ticket <ArrowRight className="size-4" aria-hidden />
        </Link>
      </div>

      <WhyPanel reasoning={decision.reasoning} failedAttempts={result.failed_attempts} />

      {decision.action === 'reply' && decision.reply_text ? (
        <SuggestedReply text={decision.reply_text} />
      ) : (
        <p className="text-sm text-muted-foreground">
          A person needs to handle this one. It is now in the Escalations queue.
        </p>
      )}

      <section className="grid gap-2">
        <h3 className="text-sm font-semibold">Sources</h3>
        <SourceList sources={result.sources ?? []} citations={decision.citations ?? []} />
      </section>
    </div>
  )
}

export function WhyPanel({
  reasoning,
  failedAttempts = [],
}: {
  reasoning: string
  failedAttempts?: string[]
}) {
  return (
    <section className="rounded-lg border bg-muted/40 p-4">
      <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold">
        <Lightbulb className="size-4" aria-hidden /> Why
      </h3>
      <p className="text-sm text-muted-foreground">{reasoning}</p>
      {failedAttempts.length > 0 && (
        <div className="mt-3 text-xs text-muted-foreground">
          <p>Fell back past {failedAttempts.length} failed attempt(s):</p>
          <ul className="mt-1 list-disc pl-5">
            {failedAttempts.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

export function SuggestedReply({ text, title = 'Suggested reply' }: { text: string; title?: string }) {
  const [copied, setCopied] = useState(false)

  async function copy() {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }

  return (
    <section className="grid gap-2">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">{title}</h3>
        <Button variant="outline" size="sm" onClick={copy}>
          {copied ? <Check className="size-4" aria-hidden /> : <Copy className="size-4" aria-hidden />}
          {copied ? 'Copied' : 'Copy'}
        </Button>
      </div>
      <p className="rounded-lg border bg-background p-4 text-sm whitespace-pre-wrap">{text}</p>
    </section>
  )
}
