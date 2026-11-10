import { describe, expect, it } from 'vitest'

import { makeRecord, makeReplyRecord } from '@/components/test-data'
import { errorText, filterTickets, type StatusFilter, summarize } from '@/lib/tickets'

const replied = makeReplyRecord()
const escalated = makeRecord({ ticket_id: 'e1', owner: null })
const owned = makeRecord({ ticket_id: 'e2', owner: 'Priya' })
const resolved = makeRecord({ ticket_id: 'x1', status: 'resolved', owner: null })

describe('summarize', () => {
  it('counts each status, and open escalations with no owner', () => {
    expect(summarize([replied, escalated, owned, resolved])).toEqual({
      total: 4,
      replied: 1,
      escalated: 2,
      unassigned: 1,
      resolved: 1,
    })
  })

  it('is all zeros for no tickets', () => {
    expect(summarize([])).toEqual({ total: 0, replied: 0, escalated: 0, unassigned: 0, resolved: 0 })
  })
})

describe('filterTickets', () => {
  it('keeps everything with the all filter and an empty search', () => {
    expect(filterTickets([replied, escalated], { status: 'all', query: '  ' })).toHaveLength(2)
  })

  it('filters by status', () => {
    const ids = (status: StatusFilter) =>
      filterTickets([replied, escalated, resolved], { status, query: '' }).map((r) => r.ticket_id)
    expect(ids('replied')).toEqual(['r1'])
    expect(ids('escalated')).toEqual(['e1'])
    expect(ids('resolved')).toEqual(['x1'])
  })

  it('matches the search against subject, body, owner and email, ignoring case', () => {
    const hit = (query: string) =>
      filterTickets([replied, owned], { status: 'all', query }).map((r) => r.ticket_id)
    expect(hit('EXPORT')).toEqual(['r1'])
    expect(hit('where is')).toEqual(['r1'])
    expect(hit('priya')).toEqual(['e2'])
    expect(hit('pat@')).toEqual(['e2'])
    expect(hit('nothing-matches')).toEqual([])
  })
})

describe('errorText', () => {
  it('uses the API detail when there is one', () => {
    expect(errorText({ detail: 'ticket is already resolved' })).toBe('ticket is already resolved')
  })

  it('falls back for anything else', () => {
    expect(errorText({ detail: [{ msg: 'x' }] }, 'nope')).toBe('nope')
    expect(errorText(new Error('boom'))).toBe('Something went wrong.')
    expect(errorText(null)).toBe('Something went wrong.')
  })
})
