import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { screen, waitFor } from '@testing-library/react'
import { renderLinked } from '@/test/render-linked'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'

import { client } from '@/client/client.gen'
import { TriagePage } from '@/components/triage-page'
import { json, mockApi } from '@/test/api'

const realFetch = client.getConfig().fetch
afterEach(() => client.setConfig({ fetch: realFetch }))

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return renderLinked(
    <QueryClientProvider client={queryClient}>
      <TriagePage />
    </QueryClientProvider>,
  )
}

const replyResult = {
  decision: { action: 'reply', reasoning: 'Docs cover it.', reply_text: 'Use Export.' },
  route: 'agent',
  provider: 'claude',
  failed_attempts: [],
  ticket_id: 't1',
}

describe('TriagePage', () => {
  it('fills the form from a sample ticket', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(screen.getByRole('button', { name: 'Refund request' }))
    expect((screen.getByLabelText('Subject') as HTMLInputElement).value).toBe('Refund please')
    expect((screen.getByLabelText('Message') as HTMLTextAreaElement).value).toContain('charged twice')
  })

  it('sends the ticket and shows the reply', async () => {
    const user = userEvent.setup()
    const api = mockApi(async () => json(replyResult))
    renderPage()
    await user.type(screen.getByLabelText('Subject'), 'Export')
    await user.type(screen.getByLabelText('Message'), 'Where is export?')
    await user.click(screen.getByRole('button', { name: 'Triage ticket' }))

    expect(await screen.findByText('Use Export.')).toBeTruthy()
    const request = api.mock.calls[0][0]
    expect(new URL(request.url).pathname).toBe('/api/triage')
    expect(JSON.parse(await request.text())).toEqual({
      subject: 'Export',
      body: 'Where is export?',
      customer_email: null,
    })
  })

  it('sends the customer email when one is given', async () => {
    const user = userEvent.setup()
    const api = mockApi(async () => json(replyResult))
    renderPage()
    await user.type(screen.getByLabelText('Customer email'), 'pat@example.com')
    await user.type(screen.getByLabelText('Subject'), 'Export')
    await user.type(screen.getByLabelText('Message'), 'Where is export?')
    await user.click(screen.getByRole('button', { name: 'Triage ticket' }))
    await screen.findByText('Use Export.')
    const body = JSON.parse(await api.mock.calls[0][0].text())
    expect(body.customer_email).toBe('pat@example.com')
  })

  it('shows the escalation message for a ticket a person must handle', async () => {
    const user = userEvent.setup()
    mockApi(async () =>
      json({
        ...replyResult,
        decision: { action: 'escalate', reasoning: 'Refund.', reply_text: null },
        route: 'human',
        provider: 'rules',
      }),
    )
    renderPage()
    await user.type(screen.getByLabelText('Subject'), 'Refund')
    await user.type(screen.getByLabelText('Message'), 'Money back')
    await user.click(screen.getByRole('button', { name: 'Triage ticket' }))
    expect(await screen.findByText(/A person needs to handle this one/)).toBeTruthy()
  })

  it('shows progress while the request is in flight', async () => {
    const user = userEvent.setup()
    mockApi(() => new Promise<Response>(() => {}))
    renderPage()
    await user.type(screen.getByLabelText('Subject'), 'Export')
    await user.type(screen.getByLabelText('Message'), 'Where is export?')
    await user.click(screen.getByRole('button', { name: 'Triage ticket' }))
    expect(await screen.findByRole('button', { name: 'Deciding…' })).toBeTruthy()
    const spinner = document.querySelector('.animate-spin')
    expect(spinner).not.toBeNull()
  })

  it('shows an error when the API fails', async () => {
    const user = userEvent.setup()
    mockApi(async () => json({ detail: 'boom' }, 500))
    renderPage()
    await user.type(screen.getByLabelText('Subject'), 'Export')
    await user.type(screen.getByLabelText('Message'), 'Where is export?')
    await user.click(screen.getByRole('button', { name: 'Triage ticket' }))
    await waitFor(() =>
      expect(screen.getByText('Triage failed. Check that the API is running.')).toBeTruthy(),
    )
  })
})
