import { CheckCircle2, CircleAlert, CircleDashed, LoaderCircle } from 'lucide-react'

export type FlowStatus = 'idle' | 'running' | 'done' | 'error'

const STEPS = ['Ticket received', 'Routing rules', 'Model decides', 'Decision saved']

/** Shows where a triage request is. Steps tick off as the request moves through the system. */
export function TriageFlow({ status }: { status: FlowStatus }) {
  const doneUpTo = status === 'done' ? STEPS.length : status === 'running' ? 1 : 0
  return (
    <ol className="grid gap-3" aria-label="Triage progress">
      {STEPS.map((label, index) => {
        const finished = index < doneUpTo
        const active = status === 'running' && index === doneUpTo
        const failed = status === 'error' && index === 0
        return (
          <li key={label} className="flex items-center gap-3 text-sm">
            {failed ? (
              <CircleAlert className="size-5 text-destructive" aria-hidden />
            ) : finished ? (
              <CheckCircle2 className="size-5 text-emerald-600" aria-hidden />
            ) : active ? (
              <LoaderCircle className="size-5 animate-spin text-primary" aria-hidden />
            ) : (
              <CircleDashed className="size-5 text-muted-foreground" aria-hidden />
            )}
            <span className={finished || active ? 'font-medium' : 'text-muted-foreground'}>
              {label}
            </span>
          </li>
        )
      })}
    </ol>
  )
}
