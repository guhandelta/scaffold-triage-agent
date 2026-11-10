import type { TicketRecord } from '@/client'

export function makeRecord(overrides: Partial<TicketRecord> = {}): TicketRecord {
  return {
    ticket_id: 'abc123',
    ticket: {
      subject: 'Refund please',
      body: 'I was charged twice',
      customer_email: 'pat@example.com',
    },
    result: {
      decision: {
        action: 'escalate',
        reasoning: 'Billing dispute needs a person.',
        reply_text: null,
      },
      route: 'human',
      provider: 'rules',
      failed_attempts: [],
      ticket_id: 'abc123',
    },
    owner: null,
    ...overrides,
  }
}
