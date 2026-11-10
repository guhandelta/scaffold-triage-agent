import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { SourceList } from '@/components/source-list'
import { EXPORT_SOURCE, POLICY_SOURCE, REFUND_SOURCE } from '@/components/test-data'

describe('SourceList', () => {
  it('explains when there are no sources', () => {
    render(<SourceList sources={[]} citations={[]} />)
    expect(screen.getByText(/No support doc matched/)).toBeTruthy()
  })

  it('puts cited sections first and marks each kind', () => {
    render(
      <SourceList
        sources={[POLICY_SOURCE, REFUND_SOURCE, EXPORT_SOURCE]}
        citations={[REFUND_SOURCE.id]}
      />,
    )
    const items = screen.getAllByRole('listitem').map((li) => li.textContent)
    expect(items[0]).toContain('Refund requests')
    expect(items[0]).toContain('Cited')
    expect(items[0]).toContain('Handled by a person')
    expect(items[0]).toContain('match 7.1')
    expect(items[1]).toContain('Agent policy')
    expect(items[2]).toContain(EXPORT_SOURCE.id)
    expect(screen.getAllByText('Cited')).toHaveLength(1)
  })
})
