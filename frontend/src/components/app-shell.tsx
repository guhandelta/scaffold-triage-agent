import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { Bot } from 'lucide-react'
import type { ReactNode } from 'react'

import { healthOptions } from '@/client/@tanstack/react-query.gen'
import { Badge } from '@/components/ui/badge'
import { ViewerSwitcher } from '@/components/viewer-switcher'

const NAV = [
  { to: '/', label: 'Triage' },
  { to: '/tickets', label: 'Tickets' },
  { to: '/escalations', label: 'Escalations' },
] as const

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-svh bg-gradient-to-b from-muted/50 to-background">
      <header className="sticky top-0 z-10 border-b bg-background/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <div className="flex items-center gap-6">
            <Link to="/" className="flex items-center gap-2 font-semibold">
              <span className="grid size-8 place-items-center rounded-lg bg-primary text-primary-foreground">
                <Bot className="size-5" aria-hidden />
              </span>
              <span className="grid leading-tight">
                Triage Agent
                <Organization />
              </span>
            </Link>
            <nav aria-label="Main" className="flex gap-1">
              {NAV.map((item) => (
                <Link
                  key={item.to}
                  to={item.to}
                  className="rounded-md px-3 py-1.5 text-sm text-muted-foreground transition hover:bg-muted hover:text-foreground"
                  activeProps={{ className: 'bg-muted text-foreground font-medium' }}
                  activeOptions={{ exact: item.to === '/' }}
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <ViewerSwitcher />
            <Health />
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
    </div>
  )
}

function Health() {
  const { data, isError } = useQuery(healthOptions())
  if (isError) return <Badge variant="destructive">API offline</Badge>
  if (!data) return null
  return (
    <Badge variant="secondary" className="gap-2">
      <span className="size-2 rounded-full bg-emerald-500" aria-hidden /> API ok · {data.agent}
    </Badge>
  )
}

function Organization() {
  const { data } = useQuery(healthOptions())
  if (!data?.organization) return null
  return <span className="text-xs font-normal text-muted-foreground">{data.organization}</span>
}
