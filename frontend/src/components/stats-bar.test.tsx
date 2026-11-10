import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { StatsBar } from '@/components/stats-bar'

describe('StatsBar', () => {
  it('shows total, replied, escalated, unassigned and resolved counts in that order', () => {
    const { container } = render(
      <StatsBar stats={{ total: 6, replied: 3, escalated: 2, unassigned: 1, resolved: 1 }} />,
    )
    const values = Array.from(container.querySelectorAll('dd')).map((dd) => dd.textContent)
    expect(values).toEqual(['6', '3', '2', '1', '1'])
  })
})
