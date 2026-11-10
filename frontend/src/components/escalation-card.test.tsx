import { screen } from '@testing-library/react'
import { renderLinked } from '@/test/render-linked'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { EscalationCard } from '@/components/escalation-card'
import { makeRecord } from '@/components/test-data'

describe('EscalationCard', () => {
  it('shows the ticket, the reason, and that it is unassigned', () => {
    renderLinked(<EscalationCard record={makeRecord()} assigning={false} onAssign={vi.fn()} />)
    expect(screen.getByText('Refund please')).toBeTruthy()
    expect(screen.getByText('I was charged twice')).toBeTruthy()
    expect(screen.getByText('Billing dispute needs a person.')).toBeTruthy()
    expect(screen.getByText('Unassigned')).toBeTruthy()
    expect(screen.getByText(/pat@example.com/)).toBeTruthy()
  })

  it('shows the owner when one is assigned', () => {
    renderLinked(
      <EscalationCard
        record={makeRecord({ owner: 'Priya' })}
        assigning={false}
        onAssign={vi.fn()}
      />,
    )
    expect(screen.getByText('Owner: Priya')).toBeTruthy()
  })

  it('leaves out the email line when the customer gave none', () => {
    const record = makeRecord()
    record.ticket.customer_email = null
    renderLinked(<EscalationCard record={record} assigning={false} onAssign={vi.fn()} />)
    expect(screen.queryByText(/pat@example.com/)).toBeNull()
    expect(screen.getByText(/Route: human/)).toBeTruthy()
  })

  it('keeps Assign disabled until a name is typed', async () => {
    const user = userEvent.setup()
    renderLinked(<EscalationCard record={makeRecord()} assigning={false} onAssign={vi.fn()} />)
    const button = screen.getByRole('button', { name: 'Assign' }) as HTMLButtonElement
    expect(button.disabled).toBe(true)
    await user.type(screen.getByLabelText('Owner'), '   ')
    expect(button.disabled).toBe(true)
    await user.clear(screen.getByLabelText('Owner'))
    await user.type(screen.getByLabelText('Owner'), 'Priya')
    expect(button.disabled).toBe(false)
  })

  it('sends the trimmed name when submitted', async () => {
    const user = userEvent.setup()
    const onAssign = vi.fn()
    renderLinked(<EscalationCard record={makeRecord()} assigning={false} onAssign={onAssign} />)
    await user.type(screen.getByLabelText('Owner'), '  Priya  ')
    await user.click(screen.getByRole('button', { name: 'Assign' }))
    expect(onAssign).toHaveBeenCalledWith('Priya')
  })

  it('does nothing on submit when the name is only spaces', async () => {
    const onAssign = vi.fn()
    renderLinked(<EscalationCard record={makeRecord()} assigning={false} onAssign={onAssign} />)
    const form = screen.getByRole('button', { name: 'Assign' }).closest('form')!
    // Submit directly: the disabled button cannot be clicked, but Enter in the field can.
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    expect(onAssign).not.toHaveBeenCalled()
  })

  it('shows progress and disables the button while assigning', () => {
    renderLinked(<EscalationCard record={makeRecord()} assigning onAssign={vi.fn()} />)
    const button = screen.getByRole('button', { name: 'Assigning…' }) as HTMLButtonElement
    expect(button.disabled).toBe(true)
  })
})

describe('EscalationCard link', () => {
  it('links the subject to the ticket page and shows the decision in force', () => {
    const record = makeRecord({
      override: { action: 'escalate', reasoning: 'Overridden by Lee: VIP', reply_text: null, citations: [] },
    })
    renderLinked(<EscalationCard record={record} assigning={false} onAssign={vi.fn()} />)
    expect(screen.getByRole('link', { name: 'Refund please' }).getAttribute('href')).toBe('/tickets/abc123')
    expect(screen.getByText('Overridden by Lee: VIP')).toBeTruthy()
  })
})
