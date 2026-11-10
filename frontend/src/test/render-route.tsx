import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  RouterProvider,
  useRouterState,
} from '@tanstack/react-router'
import { render } from '@testing-library/react'
import type { ReactNode } from 'react'

function Location() {
  const path = useRouterState({ select: (s) => s.location.pathname })
  return <p>at {path}</p>
}

/**
 * Render a component at "/" inside a real in-memory router and a fresh query client, so
 * links work. Every other path renders "at <path>", which lets tests check where a link goes.
 */
export function renderRoute(element: ReactNode) {
  const root = createRootRoute({ component: Outlet })
  const home = createRoute({ getParentRoute: () => root, path: '/', component: () => element })
  const other = createRoute({ getParentRoute: () => root, path: '$', component: Location })
  const router = createRouter({
    routeTree: root.addChildren([home, other]),
    history: createMemoryHistory({ initialEntries: ['/'] }),
  })
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const view = render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return { ...view, router, queryClient }
}
