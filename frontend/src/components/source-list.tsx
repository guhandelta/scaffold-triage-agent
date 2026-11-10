import { BookOpen } from 'lucide-react'

import type { Source } from '@/client'
import { Badge } from '@/components/ui/badge'

type Props = {
  sources: Source[]
  citations: string[]
}

/** The doc sections the agent read for a ticket, with the ones it cited marked first. */
export function SourceList({ sources, citations }: Props) {
  if (sources.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No support doc matched this ticket, so the agent had nothing to answer from.
      </p>
    )
  }
  const cited = new Set(citations)
  const ordered = [...sources].sort((a, b) => Number(cited.has(b.id)) - Number(cited.has(a.id)))

  return (
    <ol className="grid gap-3" aria-label="Sources">
      {ordered.map((source) => (
        <li
          key={source.id}
          className={`rounded-lg border p-3 text-sm ${cited.has(source.id) ? 'border-primary/40 bg-primary/5' : 'bg-background'}`}
        >
          <div className="flex flex-wrap items-center gap-2">
            <BookOpen className="size-4 text-muted-foreground" aria-hidden />
            <span className="font-medium">
              {source.title} / {source.heading}
            </span>
            {cited.has(source.id) && <Badge>Cited</Badge>}
            {source.human_only && <Badge variant="outline">Handled by a person</Badge>}
            {source.policy && <Badge variant="outline">Agent policy</Badge>}
          </div>
          <p className="mt-2 text-muted-foreground">{source.text}</p>
          <p className="mt-2 font-mono text-xs text-muted-foreground">
            {source.id} · match {source.score.toFixed(1)}
          </p>
        </li>
      ))}
    </ol>
  )
}
