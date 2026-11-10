import type { Source, TicketRecord, TriageResult } from '@/client'

export const EXPORT_SOURCE: Source = {
  id: 'product/export-and-import#export-your-data',
  area: 'product',
  title: 'Export and import',
  heading: 'Export your data',
  text: 'Open Settings, then Export.',
  human_only: false,
  policy: false,
  score: 9.5,
}

export const REFUND_SOURCE: Source = {
  id: 'billing/refunds#refund-requests',
  area: 'billing',
  title: 'Refunds and cancellations',
  heading: 'Refund requests',
  text: 'A person reviews every refund.',
  human_only: true,
  policy: false,
  score: 7.1,
}

export const POLICY_SOURCE: Source = {
  id: 'policies/escalation-policy#answer-only-from-the-docs',
  area: 'policies',
  title: 'Escalation policy',
  heading: 'Answer only from the docs',
  text: 'Cite what you use.',
  human_only: false,
  policy: true,
  score: 1.2,
}

export function makeResult(overrides: Partial<TriageResult> = {}): TriageResult {
  return {
    decision: {
      action: 'escalate',
      reasoning: 'Billing dispute needs a person.',
      reply_text: null,
      citations: [],
    },
    route: 'human',
    provider: 'rules',
    failed_attempts: [],
    ticket_id: 'abc123',
    sources: [],
    ...overrides,
  }
}

export function makeRecord(overrides: Partial<TicketRecord> = {}): TicketRecord {
  const result = overrides.result ?? makeResult({ ticket_id: overrides.ticket_id ?? 'abc123' })
  return {
    ticket_id: 'abc123',
    ticket: {
      subject: 'Refund please',
      body: 'I was charged twice',
      customer_email: 'pat@example.com',
    },
    status: result.decision.action === 'reply' ? 'replied' : 'escalated',
    owner: null,
    override: null,
    confirmed_by: null,
    notes: [],
    history: [],
    ...overrides,
    result,
    decision: overrides.override ?? overrides.decision ?? result.decision,
  }
}

export function makeReplyRecord(overrides: Partial<TicketRecord> = {}): TicketRecord {
  return makeRecord({
    ticket_id: 'r1',
    ticket: { subject: 'Export question', body: 'Where is export?', customer_email: null },
    result: makeResult({
      ticket_id: 'r1',
      route: 'agent',
      provider: 'claude',
      decision: {
        action: 'reply',
        reasoning: 'The export doc covers it.',
        reply_text: 'Hi, open Settings, then Export.',
        citations: [EXPORT_SOURCE.id],
      },
      sources: [EXPORT_SOURCE, POLICY_SOURCE],
    }),
    ...overrides,
  })
}
