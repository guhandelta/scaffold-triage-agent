import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'

import { client } from '@/client/client.gen'
import { makeRecord } from '@/components/test-data'
import { TicketsPage } from '@/components/tickets-page'
import { json, mockApi } from '@/test/api'

const realFetch = client.getConfig().fetch
afterEach(() => client.setConfig({ fetch: realFetch }))

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <TicketsPage />
    </QueryClientProvider>,
  )
}

describe('TicketsPage', () => {
  it('shows the stats and the ticket list from the API', async () => {
    const api = mockApi(async () => json([makeRecord({ ticket_id: 'e1', owner: null })]))
    renderPage()
    expect(await screen.findByText('Refund please')).toBeTruthy()
    expect(new URL(api.mock.calls[0][0].url).pathname).toBe('/api/tickets')
    expect(screen.getByText('Need an owner')).toBeTruthy()
  })

  it('shows the empty state when there are no tickets', async () => {
    mockApi(async () => json([]))
    renderPage()
    expect(await screen.findByText(/No tickets yet/)).toBeTruthy()
    expect(screen.getByText('Need an owner')).toBeTruthy()
    expect(screen.getAllByText('0').length).toBeGreaterThan(0)
  })

  it('shows an error when the list cannot load', async () => {
    mockApi(async () => json({ detail: 'boom' }, 500))
    renderPage()
    expect(await screen.findByText('Could not load tickets.')).toBeTruthy()
  })

  it('narrows the list with the filter buttons', async () => {
    const user = userEvent.setup()
    mockApi(async () =>
      json([
        makeRecord({ ticket_id: 'e1', ticket: { subject: 'Refund please', body: 'x' } }),
        makeRecord({
          ticket_id: 'r1',
          ticket: { subject: 'Export question', body: 'y' },
          result: {
            decision: { action: 'reply', reasoning: 'ok', reply_text: 'Hi' },
            route: 'agent',
            provider: 'claude',
            failed_attempts: [],
            ticket_id: 'r1',
          },
        }),
      ]),
    )
    renderPage()
    expect(await screen.findByText('Export question')).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Escalated' }))
    expect(screen.queryByText('Export question')).toBeNull()
    expect(screen.getByText('Refund please')).toBeTruthy()
  })
})
