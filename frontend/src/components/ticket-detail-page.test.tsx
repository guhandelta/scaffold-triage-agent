import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'

import type { TicketRecord } from '@/client'
import { client } from '@/client/client.gen'
import { makeRecord, makeReplyRecord, REFUND_SOURCE } from '@/components/test-data'
import { TicketDetailPage } from '@/components/ticket-detail-page'
import { json, mockApi } from '@/test/api'
import { renderLinked } from '@/test/render-linked'
import { renderRoute } from '@/test/render-route'

const realFetch = client.getConfig().fetch
afterEach(() => client.setConfig({ fetch: realFetch }))

const REVIEWER = {
  name: 'Reviewer',
  role: 'reviewer',
  permissions: ['assign', 'confirm', 'note', 'override', 'resolve'],
}
const AT = '2026-11-10T09:30:00Z'

function serve(record: TicketRecord | Response, me: unknown = REVIEWER) {
  return mockApi(async (request) => {
    const path = new URL(request.url).pathname
    if (path === '/api/me') return me instanceof Response ? me : json(me)
    return record instanceof Response ? record : json(record)
  })
}

describe('TicketDetailPage', () => {
  it('shows loading, then the ticket, its decision, sources, notes and history', async () => {
    const record = makeReplyRecord({
      owner: 'Priya',
      notes: [{ author: 'Lee', text: 'Checked the plan.', at: AT }],
      history: [{ kind: 'decided', detail: 'reply by claude', actor: 'claude', at: AT }],
    })
    const api = serve(record)
    renderLinked(<TicketDetailPage ticketId="r1" />)
    expect(screen.getByText('Loading ticket…')).toBeTruthy()
    expect(await screen.findByRole('heading', { name: 'Export question' })).toBeTruthy()
    expect(api.mock.calls.some(([r]) => new URL(r.url).pathname === '/api/tickets/r1')).toBe(true)
    expect(screen.getByText('#r1')).toBeTruthy()
    expect(screen.getByText('Owner: Priya')).toBeTruthy()
    expect(screen.getByText('Where is export?')).toBeTruthy()
    expect(screen.getByText('The export doc covers it.')).toBeTruthy()
    expect(screen.getByText('Hi, open Settings, then Export.')).toBeTruthy()
    expect(screen.getByText(/decided by claude/)).toBeTruthy()
    expect(within(screen.getByRole('list', { name: 'Sources' })).getAllByText('Cited')).toHaveLength(1)
    expect(screen.getByText('Checked the plan.')).toBeTruthy()
    expect(screen.getByText(/^Lee ·/)).toBeTruthy()
    expect(within(screen.getByRole('list', { name: 'History' })).getByText('reply by claude')).toBeTruthy()
    expect(await screen.findByRole('button', { name: 'Confirm reply' })).toBeTruthy()
    expect(screen.getByRole('link', { name: /All tickets/ }).getAttribute('href')).toBe('/tickets')
  })

  it('shows an escalation with no reply, email or owner, and empty notes', async () => {
    const record = makeRecord({
      result: { ...makeRecord().result, sources: [REFUND_SOURCE] },
    })
    record.ticket.customer_email = null
    serve(record, { name: 'V', role: 'viewer', permissions: [] })
    renderLinked(<TicketDetailPage ticketId="abc123" />)
    expect(await screen.findByText('No reply is sent. A person handles this ticket.')).toBeTruthy()
    expect(screen.getByText('No owner')).toBeTruthy()
    expect(screen.getByText('No notes yet.')).toBeTruthy()
    expect(screen.getByText('No history yet.')).toBeTruthy()
    expect(screen.getByText('Handled by a person')).toBeTruthy()
    expect(await screen.findByText(/Your role \(viewer\)/)).toBeTruthy()
  })

  it('shows a reviewer override next to the agent original', async () => {
    const agent = makeRecord()
    const record = makeRecord({
      status: 'replied',
      override: { action: 'reply', reasoning: 'Overridden by Lee: fine', reply_text: 'Sent.', citations: [] },
      result: { ...agent.result, decision: { ...agent.result.decision, reply_text: 'agent draft' } },
    })
    serve(record)
    renderLinked(<TicketDetailPage ticketId="abc123" />)
    expect(await screen.findByText('Changed by a reviewer')).toBeTruthy()
    expect(screen.getByText('Overridden by Lee: fine')).toBeTruthy()
    expect(screen.getByText('Sent.')).toBeTruthy()
    expect(screen.getByText("The agent's original decision")).toBeTruthy()
    expect(screen.getByText('Billing dispute needs a person.')).toBeTruthy()
    expect(screen.getByText('agent draft')).toBeTruthy()
  })

  it('leaves out the original reply when the agent had none', async () => {
    serve(
      makeRecord({
        status: 'escalated',
        override: { action: 'escalate', reasoning: 'Overridden', reply_text: null, citations: [] },
      }),
    )
    renderLinked(<TicketDetailPage ticketId="abc123" />)
    expect(await screen.findByText("The agent's original decision")).toBeTruthy()
  })

  it('handles old records with no lists', async () => {
    const record = makeRecord()
    delete record.notes
    delete record.history
    delete record.result.sources
    delete record.result.decision.citations
    serve(record)
    renderLinked(<TicketDetailPage ticketId="abc123" />)
    expect(await screen.findByText('No notes yet.')).toBeTruthy()
    expect(screen.getByText(/No support doc matched/)).toBeTruthy()
  })

  it('shows the API reason when the ticket cannot load', async () => {
    serve(json({ detail: 'ticket not found' }, 404))
    renderLinked(<TicketDetailPage ticketId="nope" />)
    expect(await screen.findByText('ticket not found')).toBeTruthy()
  })

  it('falls back to a plain message for other errors', async () => {
    serve(new Response('down', { status: 500 }))
    renderLinked(<TicketDetailPage ticketId="nope" />)
    expect(await screen.findByText('Could not load this ticket.')).toBeTruthy()
  })

  it('says when permissions are loading or could not be checked', async () => {
    mockApi(async (request) =>
      new URL(request.url).pathname === '/api/me'
        ? new Promise<Response>(() => {})
        : json(makeRecord()),
    )
    renderLinked(<TicketDetailPage ticketId="abc123" />)
    expect(await screen.findByText('Checking your permissions…')).toBeTruthy()
  })

  it('reports a failed permissions check', async () => {
    serve(makeRecord(), json({ detail: 'unknown role' }, 400))
    renderLinked(<TicketDetailPage ticketId="abc123" />)
    expect(await screen.findByText('Could not check your permissions.')).toBeTruthy()
  })

  it('refreshes the page after a review action', async () => {
    const user = userEvent.setup()
    const before = makeRecord({ history: [] })
    const after = makeRecord({
      status: 'resolved',
      history: [{ kind: 'resolved', detail: 'Marked as resolved', actor: 'Reviewer', at: AT }],
    })
    mockApi(async (request) => {
      const path = new URL(request.url).pathname
      if (path === '/api/me') return json(REVIEWER)
      return json(request.method === 'POST' ? after : before)
    })
    renderRoute(<TicketDetailPage ticketId="abc123" />)
    await user.click(await screen.findByRole('button', { name: 'Mark resolved' }))
    expect(await screen.findByText('Marked as resolved')).toBeTruthy()
    expect(screen.getByText('Resolved')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Mark resolved' })).toBeNull()
  })
})
