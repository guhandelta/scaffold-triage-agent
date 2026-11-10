import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { DecisionBadge, StatusBadge } from '@/components/decision-badge'

describe('DecisionBadge', () => {
  it('labels a reply as Replied', () => {
    render(<DecisionBadge action="reply" />)
    expect(screen.getByText('Replied')).toBeTruthy()
  })

  it('labels an escalation as Escalated', () => {
    render(<DecisionBadge action="escalate" />)
    expect(screen.getByText('Escalated')).toBeTruthy()
  })
})

describe('StatusBadge', () => {
  it.each([
    ['replied', 'Replied'],
    ['escalated', 'Escalated'],
    ['resolved', 'Resolved'],
  ] as const)('labels %s as %s', (status, label) => {
    render(<StatusBadge status={status} />)
    expect(screen.getByText(label)).toBeTruthy()
  })
})
