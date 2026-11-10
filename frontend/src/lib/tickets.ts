import type { TicketRecord, TicketStatus } from '@/client'

export type StatusFilter = 'all' | TicketStatus

export type Stats = {
  total: number
  replied: number
  escalated: number
  unassigned: number
  resolved: number
}

/** Counts shown in the stats bar. Open escalations without an owner still need one. */
export function summarize(records: TicketRecord[]): Stats {
  const stats: Stats = { total: records.length, replied: 0, escalated: 0, unassigned: 0, resolved: 0 }
  for (const record of records) {
    stats[record.status] += 1
    if (record.status === 'escalated' && !record.owner) stats.unassigned += 1
  }
  return stats
}

/** Filter by status, then match the search text against subject, body, owner and email. */
export function filterTickets(
  records: TicketRecord[],
  { status, query }: { status: StatusFilter; query: string },
): TicketRecord[] {
  const needle = query.trim().toLowerCase()
  return records.filter((record) => {
    if (status !== 'all' && record.status !== status) return false
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

/** The message to show for a failed API call. FastAPI errors carry a `detail`. */
export function errorText(error: unknown, fallback = 'Something went wrong.'): string {
  if (error && typeof error === 'object' && 'detail' in error) {
    const detail = (error as { detail: unknown }).detail
    if (typeof detail === 'string') return detail
  }
  return fallback
}
