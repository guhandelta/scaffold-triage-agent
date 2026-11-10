import { Bot, CheckCircle2, ShieldAlert, UserX } from 'lucide-react'

import type { Stats } from '@/lib/tickets'

const ITEMS = [
  { key: 'total', label: 'Tickets', icon: Bot, tone: 'text-primary' },
  { key: 'replied', label: 'Replied by agent', icon: Bot, tone: 'text-emerald-600' },
  { key: 'escalated', label: 'Open escalations', icon: ShieldAlert, tone: 'text-amber-600' },
  { key: 'unassigned', label: 'Need an owner', icon: UserX, tone: 'text-destructive' },
  { key: 'resolved', label: 'Resolved', icon: CheckCircle2, tone: 'text-sky-600' },
] as const

export function StatsBar({ stats }: { stats: Stats }) {
  return (
    <dl className="grid grid-cols-2 gap-3 md:grid-cols-5">
      {ITEMS.map(({ key, label, icon: Icon, tone }) => (
        <div key={key} className="rounded-xl border bg-card p-4 shadow-sm">
          <dt className="flex items-center gap-2 text-xs text-muted-foreground">
            <Icon className={`size-4 ${tone}`} aria-hidden /> {label}
          </dt>
          <dd className="mt-1 text-2xl font-semibold tabular-nums">{stats[key]}</dd>
        </div>
      ))}
    </dl>
  )
}
