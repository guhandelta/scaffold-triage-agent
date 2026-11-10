import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  CircleDot,
  GitBranch,
  Inbox,
  MessageSquare,
  Pencil,
  ShieldCheck,
  UserPlus,
} from 'lucide-react'

import type { HistoryEvent } from '@/client'

const ICONS: Record<string, typeof CircleDot> = {
  received: Inbox,
  routed: GitBranch,
  retrieved: BookOpen,
  error: AlertTriangle,
  grounding: ShieldCheck,
  decided: CheckCircle2,
  assigned: UserPlus,
  confirmed: CheckCircle2,
  overridden: Pencil,
  note: MessageSquare,
  resolved: CheckCircle2,
}

export function formatTime(at: string | undefined): string {
  if (!at) return ''
  return new Date(at).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

/** Everything that happened to a ticket, oldest first, with who did it. */
export function TicketHistory({ events }: { events: HistoryEvent[] }) {
  if (events.length === 0) return <p className="text-sm text-muted-foreground">No history yet.</p>
  return (
    <ol className="relative grid gap-4 border-l pl-6" aria-label="History">
      {events.map((event, index) => {
        const Icon = ICONS[event.kind] ?? CircleDot
        const tone = event.kind === 'error' ? 'text-destructive' : 'text-primary'
        return (
          <li key={`${event.at}-${index}`} className="relative text-sm">
            <span className="absolute top-0.5 -left-[33px] grid size-5 place-items-center rounded-full border bg-background">
              <Icon className={`size-3 ${tone}`} aria-hidden />
            </span>
            <p>
              <span className="font-medium capitalize">{event.kind}</span>{' '}
              <span className="text-muted-foreground">by {event.actor}</span>
            </p>
            <p className="break-words text-muted-foreground">{event.detail}</p>
            <time className="text-xs text-muted-foreground" dateTime={event.at}>
              {formatTime(event.at)}
            </time>
          </li>
        )
      })}
    </ol>
  )
}
