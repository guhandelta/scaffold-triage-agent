import { screen } from '@testing-library/react'
import { renderLinked } from '@/test/render-linked'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import type { TicketRecord } from '@/client'
import { makeRecord, makeReplyRecord } from '@/components/test-data'
import { TicketList } from '@/components/ticket-list'

const escalated: TicketRecord = makeRecord({
  ticket_id: 'e1',
  ticket: { subject: 'Refund please', body: 'charged twice', customer_email: null },
  owner: 'Priya',
})
const replied: TicketRecord = makeRecord({
  ticket_id: 'r1',
  ticket: { subject: 'Export question', body: 'where is export', customer_email: null },
  owner: null,
  result: {
    decision: { action: 'reply', reasoning: 'ok', reply_text: 'Hi' },
    route: 'agent',
    provider: 'claude',
    failed_attempts: [],
    ticket_id: 'r1',
  },
})

const base = { isPending: false, isError: false }

describe('TicketList', () => {
  it('shows a loading line', () => {
    renderLinked(<TicketList records={undefined} isPending isError={false} />)
    expect(screen.getByText('Loading tickets…')).toBeTruthy()
  })

  it('shows an error line', () => {
    renderLinked(<TicketList records={undefined} isPending={false} isError />)
    expect(screen.getByText('Could not load tickets.')).toBeTruthy()
  })

  it('shows the empty state for no tickets', () => {
    renderLinked(<TicketList records={[]} {...base} />)
    expect(screen.getByText(/No tickets yet/)).toBeTruthy()
  })

  it('lists each ticket with its provider, owner and id', () => {
    renderLinked(<TicketList records={[escalated, replied]} {...base} />)
    expect(screen.getByText('Refund please')).toBeTruthy()
    expect(screen.getByText('Owner: Priya')).toBeTruthy()
    expect(screen.getByText('No owner')).toBeTruthy()
    expect(screen.getByText('#r1')).toBeTruthy()
    expect(screen.getByText('Decided by claude')).toBeTruthy()
    expect(screen.getByText('Decided by rules')).toBeTruthy()
  })

  it('filters by decision with the buttons', async () => {
    const user = userEvent.setup()
    renderLinked(<TicketList records={[escalated, replied]} {...base} />)
    await user.click(screen.getByRole('button', { name: 'Replied' }))
    expect(screen.queryByText('Refund please')).toBeNull()
    expect(screen.getByText('Export question')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Replied' }).getAttribute('aria-pressed')).toBe('true')
    await user.click(screen.getByRole('button', { name: 'All' }))
    expect(screen.getByText('Refund please')).toBeTruthy()
  })

  it('searches as you type and says when nothing matches', async () => {
    const user = userEvent.setup()
    renderLinked(<TicketList records={[escalated, replied]} {...base} />)
    await user.type(screen.getByLabelText('Search tickets'), 'priya')
    expect(screen.getByText('Refund please')).toBeTruthy()
    expect(screen.queryByText('Export question')).toBeNull()
    await user.clear(screen.getByLabelText('Search tickets'))
    await user.type(screen.getByLabelText('Search tickets'), 'zzz')
    expect(screen.getByText('No tickets match these filters.')).toBeTruthy()
  })
})

describe('TicketList links and badges', () => {
  it('links each ticket to its page and shows citations and overrides', () => {
    const changed = makeReplyRecord({
      ticket_id: 'c1',
      override: { action: 'reply', reasoning: 'x', reply_text: 'y', citations: [] },
    })
    renderLinked(<TicketList records={[changed]} {...base} />)
    expect(screen.getByRole('link').getAttribute('href')).toBe('/tickets/c1')
    expect(screen.getByText('Cites 1 doc(s)')).toBeTruthy()
    expect(screen.getByText('Changed by a reviewer')).toBeTruthy()
  })

  it('filters resolved tickets', async () => {
    const user = userEvent.setup()
    renderLinked(
      <TicketList records={[escalated, makeRecord({ ticket_id: 'x', status: 'resolved', ticket: { subject: 'Done one', body: 'b' } })]} {...base} />,
    )
    await user.click(screen.getByRole('button', { name: 'Resolved' }))
    expect(screen.getByText('Done one')).toBeTruthy()
    expect(screen.queryByText('Refund please')).toBeNull()
  })
})
