import { screen } from '@testing-library/react'
import { renderLinked } from '@/test/render-linked'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { EscalationsView } from '@/components/escalations-view'
import { makeRecord } from '@/components/test-data'

const base = {
  isPending: false,
  isError: false,
  assigning: false,
  assignFailed: false,
}

describe('EscalationsView', () => {
  it('shows a loading line while the queue loads', () => {
    renderLinked(<EscalationsView {...base} items={undefined} isPending onAssign={vi.fn()} />)
    expect(screen.getByText('Loading escalations…')).toBeTruthy()
  })

  it('shows an error line when the queue fails to load', () => {
    renderLinked(<EscalationsView {...base} items={undefined} isError onAssign={vi.fn()} />)
    expect(screen.getByText('Could not load escalations.')).toBeTruthy()
  })

  it('shows an empty state when nothing needs a person', () => {
    renderLinked(<EscalationsView {...base} items={[]} onAssign={vi.fn()} />)
    expect(screen.getByText('Nothing needs a person right now.')).toBeTruthy()
  })

  it('treats a missing list as empty', () => {
    renderLinked(<EscalationsView {...base} items={undefined} onAssign={vi.fn()} />)
    expect(screen.getByText('Nothing needs a person right now.')).toBeTruthy()
  })

  it('lists each escalation and passes its id when assigned', async () => {
    const user = userEvent.setup()
    const onAssign = vi.fn()
    const items = [
      makeRecord({ ticket_id: 'one', ticket: { subject: 'First', body: 'a' } }),
      makeRecord({ ticket_id: 'two', ticket: { subject: 'Second', body: 'b' } }),
    ]
    renderLinked(<EscalationsView {...base} items={items} onAssign={onAssign} />)
    expect(screen.getByText('First')).toBeTruthy()
    expect(screen.getByText('Second')).toBeTruthy()

    const inputs = screen.getAllByLabelText('Owner')
    await user.type(inputs[1], 'Priya')
    await user.click(screen.getAllByRole('button', { name: 'Assign' })[1])
    expect(onAssign).toHaveBeenCalledWith('two', 'Priya')
  })

  it('warns when the last assignment failed', () => {
    renderLinked(
      <EscalationsView
        {...base}
        items={[makeRecord()]}
        assignFailed
        onAssign={vi.fn()}
      />,
    )
    expect(screen.getByText('Could not assign that ticket.')).toBeTruthy()
  })

  it('does not warn when assignments are fine', () => {
    renderLinked(<EscalationsView {...base} items={[makeRecord()]} onAssign={vi.fn()} />)
    expect(screen.queryByText('Could not assign that ticket.')).toBeNull()
  })
})
