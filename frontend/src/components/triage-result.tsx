import { Check, Copy, Lightbulb } from 'lucide-react'
import { useState } from 'react'

import type { TriageResult } from '@/client'
import { DecisionBadge } from '@/components/decision-badge'
import { Button } from '@/components/ui/button'

export function TriageResultPanel({ result }: { result: TriageResult }) {
  const { decision } = result

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <DecisionBadge action={decision.action} />
        <span className="text-xs text-muted-foreground">
          Routed {result.route} · decided by {result.provider}
        </span>
      </div>

      <section className="rounded-lg border bg-muted/40 p-4">
        <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold">
          <Lightbulb className="size-4" aria-hidden /> Why
        </h3>
        <p className="text-sm text-muted-foreground">{decision.reasoning}</p>
        {result.failed_attempts.length > 0 && (
          <div className="mt-3 text-xs text-muted-foreground">
            <p>Fell back past {result.failed_attempts.length} failed attempt(s):</p>
            <ul className="mt-1 list-disc pl-5">
              {result.failed_attempts.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          </div>
        )}
      </section>

      {decision.action === 'reply' && decision.reply_text ? (
        <SuggestedReply text={decision.reply_text} />
      ) : (
        <p className="text-sm text-muted-foreground">
          A person needs to handle this one. It is now in the Escalations queue.
        </p>
      )}
    </div>
  )
}

function SuggestedReply({ text }: { text: string }) {
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
        <h3 className="text-sm font-semibold">Suggested reply</h3>
        <Button variant="outline" size="sm" onClick={copy}>
          {copied ? <Check className="size-4" aria-hidden /> : <Copy className="size-4" aria-hidden />}
          {copied ? 'Copied' : 'Copy'}
        </Button>
      </div>
      <p className="rounded-lg border bg-background p-4 text-sm whitespace-pre-wrap">{text}</p>
    </section>
  )
}
