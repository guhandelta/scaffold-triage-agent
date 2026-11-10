import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  createMemoryHistory,
  createRootRoute,
  createRouter,
  RouterContextProvider,
} from '@tanstack/react-router'
import { render, type RenderOptions } from '@testing-library/react'
import type { ReactElement, ReactNode } from 'react'

/**
 * Render synchronously with router context, so components with `<Link>` work, and with a
 * fresh query client. Use `renderRoute` instead when a test needs to follow a link.
 */
export function renderLinked(ui: ReactElement, options?: Omit<RenderOptions, 'wrapper'>) {
  const router = createRouter({
    routeTree: createRootRoute(),
    history: createMemoryHistory({ initialEntries: ['/'] }),
  })
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <RouterContextProvider router={router}>{children}</RouterContextProvider>
      </QueryClientProvider>
    )
  }
  return { ...render(ui, { wrapper: Wrapper, ...options }), queryClient }
}
