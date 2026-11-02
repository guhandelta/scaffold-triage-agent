import type { QueryClient } from '@tanstack/react-query'
import { useQuery } from '@tanstack/react-query'
import { createRootRouteWithContext, Link, Outlet } from '@tanstack/react-router'

import { healthOptions } from '@/client/@tanstack/react-query.gen'
import { Badge } from '@/components/ui/badge'

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  component: RootLayout,
})

function RootLayout() {
  return (
    <div className="min-h-svh">
      <header className="border-b">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-4 px-4 py-3">
          <Link to="/" className="font-semibold">
            Triage Agent
          </Link>
          <Health />
        </div>
      </header>
      <main className="mx-auto max-w-3xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}

function Health() {
  const { data, isError } = useQuery(healthOptions())
  if (isError) return <Badge variant="destructive">API offline</Badge>
  if (!data) return null
  return <Badge variant="secondary">API ok · {data.agent}</Badge>
}
