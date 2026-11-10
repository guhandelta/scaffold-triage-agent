import type { TicketRecord } from '@/client'

export type DecisionFilter = 'all' | 'reply' | 'escalate'

export type Stats = {
  total: number
  replied: number
  escalated: number
  unassigned: number
}

/** Counts shown in the stats bar. Escalated tickets without an owner still need one. */
export function summarize(records: TicketRecord[]): Stats {
  let replied = 0
  let escalated = 0
  let unassigned = 0
  for (const record of records) {
    if (record.result.decision.action === 'escalate') {
      escalated += 1
      if (!record.owner) unassigned += 1
    } else {
      replied += 1
    }
  }
  return { total: records.length, replied, escalated, unassigned }
}

/** Filter by decision, then match the search text against subject, body, owner and email. */
export function filterTickets(
  records: TicketRecord[],
  { decision, query }: { decision: DecisionFilter; query: string },
): TicketRecord[] {
  const needle = query.trim().toLowerCase()
  return records.filter((record) => {
    if (decision !== 'all' && record.result.decision.action !== decision) return false
    if (!needle) return true
    const haystack = [
      record.ticket.subject,
      record.ticket.body,
      record.owner ?? '',
      record.ticket.customer_email ?? '',
    ]
      .join(' ')
      .toLowerCase()
    return haystack.includes(needle)
  })
}
