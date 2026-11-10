import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { TriageFlow, type FlowStatus } from '@/components/triage-flow'

function stepItems(status: FlowStatus) {
  const { container } = render(<TriageFlow status={status} />)
  return Array.from(container.querySelectorAll('li'))
}

describe('TriageFlow', () => {
  it('lists the four steps', () => {
    stepItems('idle')
    expect(screen.getByText('Ticket received')).toBeTruthy()
    expect(screen.getByText('Decision saved')).toBeTruthy()
  })

  it('finishes the first step and shows the second as active while running', () => {
    const items = stepItems('running')
    expect(items[0].querySelector('.text-emerald-600')).not.toBeNull()
    expect(items[1].querySelector('.animate-spin')).not.toBeNull()
    expect(items[2].querySelector('.animate-spin')).toBeNull()
  })

  it('marks every step finished when done', () => {
    const items = stepItems('done')
    for (const item of items) {
      expect(item.querySelector('.text-emerald-600')).not.toBeNull()
    }
  })

  it('marks the first step as failed on error', () => {
    const items = stepItems('error')
    expect(items[0].querySelector('.text-destructive')).not.toBeNull()
  })

  it('shows nothing finished before a request starts', () => {
    const items = stepItems('idle')
    expect(items[0].querySelector('.text-emerald-600')).toBeNull()
    expect(items[0].querySelector('.animate-spin')).toBeNull()
  })
})
