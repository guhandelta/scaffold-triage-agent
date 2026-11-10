import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { EscalationCard } from '@/components/escalation-card'
import { makeRecord } from '@/components/test-data'

describe('EscalationCard', () => {
  it('shows the ticket, the reason, and that it is unassigned', () => {
    render(<EscalationCard record={makeRecord()} assigning={false} onAssign={vi.fn()} />)
    expect(screen.getByText('Refund please')).toBeTruthy()
    expect(screen.getByText('I was charged twice')).toBeTruthy()
    expect(screen.getByText('Billing dispute needs a person.')).toBeTruthy()
    expect(screen.getByText('Unassigned')).toBeTruthy()
    expect(screen.getByText(/pat@example.com/)).toBeTruthy()
  })

  it('shows the owner when one is assigned', () => {
    render(
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
    render(<EscalationCard record={record} assigning={false} onAssign={vi.fn()} />)
    expect(screen.queryByText(/pat@example.com/)).toBeNull()
    expect(screen.getByText(/Route: human/)).toBeTruthy()
  })

  it('keeps Assign disabled until a name is typed', async () => {
    const user = userEvent.setup()
    render(<EscalationCard record={makeRecord()} assigning={false} onAssign={vi.fn()} />)
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
    render(<EscalationCard record={makeRecord()} assigning={false} onAssign={onAssign} />)
    await user.type(screen.getByLabelText('Owner'), '  Priya  ')
    await user.click(screen.getByRole('button', { name: 'Assign' }))
    expect(onAssign).toHaveBeenCalledWith('Priya')
  })

  it('does nothing on submit when the name is only spaces', async () => {
    const onAssign = vi.fn()
    render(<EscalationCard record={makeRecord()} assigning={false} onAssign={onAssign} />)
    const form = screen.getByRole('button', { name: 'Assign' }).closest('form')!
    // Submit directly: the disabled button cannot be clicked, but Enter in the field can.
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    expect(onAssign).not.toHaveBeenCalled()
  })

  it('shows progress and disables the button while assigning', () => {
    render(<EscalationCard record={makeRecord()} assigning onAssign={vi.fn()} />)
    const button = screen.getByRole('button', { name: 'Assigning…' }) as HTMLButtonElement
    expect(button.disabled).toBe(true)
  })
})
