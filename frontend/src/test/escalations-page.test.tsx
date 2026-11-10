import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { screen, waitFor } from '@testing-library/react'
import { renderLinked } from '@/test/render-linked'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { client } from '@/client/client.gen'
import { makeRecord } from '@/components/test-data'
import { EscalationsPage } from '@/components/escalations-page'
import { Route } from '@/routes/escalations'



function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

// The generated client sends requests through the `fetch` in its config, so the tests
// swap that for a mock and restore the real one afterwards.
const realFetch = client.getConfig().fetch
function mockApi(handler: (request: Request) => Promise<Response>) {
  const mock = vi.fn(handler)
  // The client calls fetch with a Request object, so the mock receives that.
  client.setConfig({ fetch: mock as unknown as typeof fetch })
  return mock
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return renderLinked(
    <QueryClientProvider client={queryClient}>
      <EscalationsPage />
    </QueryClientProvider>,
  )
}

afterEach(() => {
  client.setConfig({ fetch: realFetch })
})

describe('Escalations page', () => {
  it('is the component of the escalations route', () => {
    expect(Route.options.component).toBe(EscalationsPage)
  })

  it('loads the queue from the API and shows it', async () => {
    const api = mockApi(async () => json([makeRecord({ ticket_id: 'q1' })]))
    renderPage()
    expect(await screen.findByText('Refund please')).toBeTruthy()
    expect(new URL(api.mock.calls[0][0].url).pathname).toBe('/api/escalations')
  })

  it('shows the empty state for an empty queue', async () => {
    mockApi(async () => json([]))
    renderPage()
    expect(await screen.findByText('Nothing needs a person right now.')).toBeTruthy()
  })

  it('shows an error when the queue cannot load', async () => {
    mockApi(async () => json({ detail: 'boom' }, 500))
    renderPage()
    expect(await screen.findByText('Could not load escalations.')).toBeTruthy()
  })

  it('posts the assignment, then reloads the queue', async () => {
    const user = userEvent.setup()
    let owner: string | undefined
    const api = mockApi(async (request) => {
      if (request.method === 'POST') {
        owner = JSON.parse(await request.text()).owner
        return json(makeRecord({ ticket_id: 'q1', owner }))
      }
      return json([makeRecord({ ticket_id: 'q1', owner })])
    })
    renderPage()

    await user.type(await screen.findByLabelText('Owner'), 'Priya')
    await user.click(screen.getByRole('button', { name: 'Assign' }))

    expect(await screen.findByText('Owner: Priya')).toBeTruthy()
    const post = api.mock.calls.find(([r]) => r.method === 'POST')![0]
    expect(new URL(post.url).pathname).toBe('/api/tickets/q1/assign')
    expect(owner).toBe('Priya')
  })

  it('warns when an assignment fails', async () => {
    const user = userEvent.setup()
    mockApi(async (request) => {
      if (request.method === 'POST') return json({ detail: 'nope' }, 404)
      return json([makeRecord({ ticket_id: 'q1' })])
    })
    renderPage()
    await user.type(await screen.findByLabelText('Owner'), 'Priya')
    await user.click(screen.getByRole('button', { name: 'Assign' }))
    await waitFor(() => expect(screen.getByText('Could not assign that ticket.')).toBeTruthy())
  })
})
