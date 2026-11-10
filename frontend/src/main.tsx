import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createRouter, RouterProvider } from '@tanstack/react-router'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { client } from '@/client/client.gen'
import { installViewerHeaders } from '@/lib/user'
import { routeTree } from './routeTree.gen'
import './index.css'

// In dev, Vite proxies /api to FastAPI, so relative URLs work.
client.setConfig({ baseUrl: import.meta.env.VITE_API_URL ?? '' })
installViewerHeaders()

const queryClient = new QueryClient()
const router = createRouter({ routeTree, context: { queryClient }, defaultPreload: 'intent' })

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
)
