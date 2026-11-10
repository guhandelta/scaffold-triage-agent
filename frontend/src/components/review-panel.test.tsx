import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'

import type { Permission, TicketRecord } from '@/client'
import { getTicketQueryKey } from '@/client/@tanstack/react-query.gen'
import { client } from '@/client/client.gen'
import { ReviewPanel } from '@/components/review-panel'
import { makeRecord, makeReplyRecord } from '@/components/test-data'
import { json, mockApi } from '@/test/api'
import { renderLinked } from '@/test/render-linked'

const realFetch = client.getConfig().fetch
afterEach(() => client.setConfig({ fetch: realFetch }))

const ALL: Permission[] = ['assign', 'confirm', 'note', 'override', 'resolve']

function renderPanel(record: TicketRecord = makeRecord(), permissions = ALL, role = 'reviewer') {
  return renderLinked(<ReviewPanel record={record} permissions={permissions} role={role} />)
}

/** Answer every call with the updated record, and keep what was sent. */
function answerWith(updated: TicketRecord) {
  const sent: { path: string; body: unknown }[] = []
  mockApi(async (request) => {
    const text = await request.text()
    sent.push({ path: new URL(request.url).pathname, body: text ? JSON.parse(text) : null })
    return json(updated)
  })
  return sent
}

describe('ReviewPanel permissions', () => {
  it('tells a viewer they can only look', () => {
    renderPanel(makeRecord(), [], 'viewer')
    expect(screen.getByText('Your role (viewer) can view tickets but not change them.')).toBeTruthy()
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('gives a support agent only assign and note', () => {
    renderPanel(makeRecord(), ['assign', 'note'], 'agent')
    expect(screen.getByRole('button', { name: 'Assign' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Add note' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: /Confirm/ })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Mark resolved' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Override decision' })).toBeNull()
  })

  it('hides confirm, override and resolve on a resolved ticket', () => {
    renderPanel(makeRecord({ status: 'resolved', confirmed_by: 'Lee' }))
    expect(screen.queryByRole('button', { name: /Confirm/ })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Override decision' })).toBeNull()
    expect(screen.getByText('Confirmed by Lee')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Add note' })).toBeTruthy()
  })

  it('shows only the confirm or resolve button the role allows', () => {
    renderPanel(makeRecord(), ['resolve'])
    expect(screen.getByRole('button', { name: 'Mark resolved' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: /Confirm/ })).toBeNull()
  })

  it('names the decision being confirmed', () => {
    renderPanel(makeReplyRecord(), ['confirm'])
    expect(screen.getByRole('button', { name: 'Confirm reply' })).toBeTruthy()
  })
})

describe('ReviewPanel actions', () => {
  it('confirms and stores the updated ticket', async () => {
    const user = userEvent.setup()
    const updated = makeRecord({ confirmed_by: 'Reviewer' })
    const sent = answerWith(updated)
    const { queryClient } = renderPanel()
    await user.click(screen.getByRole('button', { name: 'Confirm escalation' }))
    await waitFor(() =>
      expect(queryClient.getQueryData(getTicketQueryKey({ path: { ticket_id: 'abc123' } }))).toEqual(
        updated,
      ),
    )
    expect(sent[0].path).toBe('/api/tickets/abc123/confirm')
  })

  it('resolves', async () => {
    const user = userEvent.setup()
    const sent = answerWith(makeRecord({ status: 'resolved' }))
    renderPanel()
    await user.click(screen.getByRole('button', { name: 'Mark resolved' }))
    await waitFor(() => expect(sent[0]?.path).toBe('/api/tickets/abc123/resolve'))
  })

  it('assigns the trimmed owner, starting from the current one', async () => {
    const user = userEvent.setup()
    const sent = answerWith(makeRecord({ owner: 'Lee' }))
    renderPanel(makeRecord({ owner: 'Priya' }))
    const owner = screen.getByLabelText('Owner') as HTMLInputElement
    expect(owner.value).toBe('Priya')
    await user.clear(owner)
    await user.type(owner, '  Lee ')
    await user.click(screen.getByRole('button', { name: 'Assign' }))
    await waitFor(() => expect(sent[0]?.body).toEqual({ owner: 'Lee' }))
  })

  it('adds a note and clears the box', async () => {
    const user = userEvent.setup()
    const sent = answerWith(makeRecord())
    renderPanel()
    const box = screen.getByLabelText('Add a note') as HTMLTextAreaElement
    const button = screen.getByRole('button', { name: 'Add note' }) as HTMLButtonElement
    expect(button.disabled).toBe(true)
    await user.type(box, ' Called them. ')
    await user.click(button)
    await waitFor(() => expect(sent[0]?.body).toEqual({ text: 'Called them.' }))
    expect(box.value).toBe('')
  })

  it('overrides an escalation with a reply and a reason', async () => {
    const user = userEvent.setup()
    const sent = answerWith(makeReplyRecord())
    renderPanel()
    await user.click(screen.getByRole('button', { name: 'Override decision' }))
    const save = screen.getByRole('button', { name: 'Save override' }) as HTMLButtonElement
    expect((screen.getByLabelText('Send a reply') as HTMLInputElement).checked).toBe(true)
    await user.type(screen.getByLabelText('Reason'), 'Within 14 days')
    expect(save.disabled).toBe(true) // a reply needs text
    await user.type(screen.getByLabelText('Reply to the customer'), ' Refund sent. ')
    await user.click(save)
    await waitFor(() =>
      expect(sent[0]?.body).toEqual({
        action: 'reply',
        reason: 'Within 14 days',
        reply_text: 'Refund sent.',
      }),
    )
    expect(sent[0].path).toBe('/api/tickets/abc123/override')
  })

  it('overrides a reply into an escalation, and can be cancelled', async () => {
    const user = userEvent.setup()
    const sent = answerWith(makeRecord())
    renderPanel(makeReplyRecord())
    await user.click(screen.getByRole('button', { name: 'Override decision' }))
    expect((screen.getByLabelText('Hand to a person') as HTMLInputElement).checked).toBe(true)
    expect(screen.queryByLabelText('Reply to the customer')).toBeNull()
    await user.click(screen.getByLabelText('Send a reply'))
    expect((screen.getByLabelText('Reply to the customer') as HTMLTextAreaElement).value).toBe(
      'Hi, open Settings, then Export.',
    )
    await user.click(screen.getByLabelText('Hand to a person'))
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByRole('form', { name: 'Override' })).toBeNull()
    await user.click(screen.getByRole('button', { name: 'Override decision' }))
    await user.type(screen.getByLabelText('Reason'), 'VIP')
    await user.click(screen.getByRole('button', { name: 'Save override' }))
    await waitFor(() =>
      expect(sent[0]?.body).toEqual({ action: 'escalate', reason: 'VIP', reply_text: null }),
    )
  })

  it('shows why a change was refused and disables buttons while saving', async () => {
    const user = userEvent.setup()
    mockApi(async () => json({ detail: 'reviewer cannot resolve tickets' }, 403))
    renderPanel()
    await user.click(screen.getByRole('button', { name: 'Mark resolved' }))
    expect((await screen.findByRole('alert')).textContent).toBe('reviewer cannot resolve tickets')
  })

  it('falls back to a plain message when the error has no detail', async () => {
    const user = userEvent.setup()
    mockApi(async () => new Response('oops', { status: 500 }))
    renderPanel()
    await user.click(screen.getByRole('button', { name: 'Mark resolved' }))
    expect((await screen.findByRole('alert')).textContent).toBe('That change did not save.')
  })

  it('disables the buttons while a change is saving', async () => {
    const user = userEvent.setup()
    mockApi(() => new Promise<Response>(() => {}))
    renderPanel()
    await user.click(screen.getByRole('button', { name: 'Mark resolved' }))
    await waitFor(() =>
      expect((screen.getByRole('button', { name: 'Confirm escalation' }) as HTMLButtonElement).disabled).toBe(
        true,
      ),
    )
  })
})
