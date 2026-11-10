import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { formatTime, TicketHistory } from '@/components/ticket-history'

const AT = '2026-11-10T09:30:00Z'

describe('TicketHistory', () => {
  it('says when there is no history', () => {
    render(<TicketHistory events={[]} />)
    expect(screen.getByText('No history yet.')).toBeTruthy()
  })

  it('lists each event with who did it and when', () => {
    render(
      <TicketHistory
        events={[
          { kind: 'received', detail: 'Subject: Refund', actor: 'system', at: AT },
          { kind: 'error', detail: 'claude: 429', actor: 'agent', at: AT },
          { kind: 'something-new', detail: 'custom', actor: 'Priya', at: AT },
        ]}
      />,
    )
    const items = screen.getAllByRole('listitem')
    expect(items).toHaveLength(3)
    expect(items[0].textContent).toContain('received')
    expect(items[0].textContent).toContain('by system')
    expect(items[1].querySelector('svg')?.getAttribute('class')).toContain('text-destructive')
    expect(items[2].textContent).toContain('by Priya')
    expect(items[0].querySelector('time')?.getAttribute('datetime')).toBe(AT)
  })
})

describe('formatTime', () => {
  it('formats a time, and gives nothing for a missing one', () => {
    expect(formatTime(AT)).toMatch(/2026/)
    expect(formatTime(undefined)).toBe('')
  })
})
