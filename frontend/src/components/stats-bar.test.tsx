import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { StatsBar } from '@/components/stats-bar'

describe('StatsBar', () => {
  it('shows total, replied, escalated and unassigned counts in that order', () => {
    const { container } = render(
      <StatsBar stats={{ total: 5, replied: 3, escalated: 2, unassigned: 1 }} />,
    )
    const values = Array.from(container.querySelectorAll('dd')).map((dd) => dd.textContent)
    expect(values).toEqual(['5', '3', '2', '1'])
  })
})
