import { describe, expect, it } from 'vitest'

import { makeRecord } from '@/components/test-data'
import { filterTickets, summarize } from '@/lib/tickets'

const replied = makeRecord({
  ticket_id: 'r1',
  ticket: { subject: 'Export', body: 'Where is export?', customer_email: null },
  result: {
    decision: { action: 'reply', reasoning: 'docs', reply_text: 'Use Export.' },
    route: 'agent',
    provider: 'claude',
    failed_attempts: [],
    ticket_id: 'r1',
  },
})
const escalated = makeRecord({ ticket_id: 'e1', owner: null })
const owned = makeRecord({ ticket_id: 'e2', owner: 'Priya' })

describe('summarize', () => {
  it('counts replies, escalations and escalations with no owner', () => {
    expect(summarize([replied, escalated, owned])).toEqual({
      total: 3,
      replied: 1,
      escalated: 2,
      unassigned: 1,
    })
  })

  it('is all zeros for no tickets', () => {
    expect(summarize([])).toEqual({ total: 0, replied: 0, escalated: 0, unassigned: 0 })
  })
})

describe('filterTickets', () => {
  it('keeps everything with the all filter and an empty search', () => {
    expect(filterTickets([replied, escalated], { decision: 'all', query: '  ' })).toHaveLength(2)
  })

  it('filters by decision', () => {
    const ids = (decision: 'reply' | 'escalate') =>
      filterTickets([replied, escalated], { decision, query: '' }).map((r) => r.ticket_id)
    expect(ids('reply')).toEqual(['r1'])
    expect(ids('escalate')).toEqual(['e1'])
  })

  it('matches the search against subject, body, owner and email, ignoring case', () => {
    const hit = (query: string) =>
      filterTickets([replied, owned], { decision: 'all', query }).map((r) => r.ticket_id)
    expect(hit('EXPORT')).toEqual(['r1'])
    expect(hit('where is')).toEqual(['r1'])
    expect(hit('priya')).toEqual(['e2'])
    expect(hit('nothing-matches')).toEqual([])
  })

  it('matches on the customer email when there is one', () => {
    const withEmail = makeRecord({ ticket_id: 'm1' })
    withEmail.ticket.customer_email = 'pat@example.com'
    expect(filterTickets([withEmail], { decision: 'all', query: 'pat@' })).toHaveLength(1)
  })
})
