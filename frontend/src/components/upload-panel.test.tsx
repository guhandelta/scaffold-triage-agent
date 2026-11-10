import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'

import { client } from '@/client/client.gen'
import { makeRecord, makeReplyRecord } from '@/components/test-data'
import { ACCEPTED, UploadPanel } from '@/components/upload-panel'
import { json, mockApi } from '@/test/api'
import { renderLinked } from '@/test/render-linked'

const realFetch = client.getConfig().fetch
afterEach(() => client.setConfig({ fetch: realFetch }))

const FILE = new File(['Export\nHow?'], 'batch.md', { type: 'text/markdown' })

describe('UploadPanel', () => {
  it('accepts the supported types and needs a file before uploading', async () => {
    const user = userEvent.setup()
    renderLinked(<UploadPanel />)
    const input = screen.getByLabelText('Ticket file') as HTMLInputElement
    expect(input.accept).toBe(ACCEPTED)
    expect(screen.getByText(/Legacy .doc files/)).toBeTruthy()
    const button = screen.getByRole('button', { name: 'Upload and triage' }) as HTMLButtonElement
    expect(button.disabled).toBe(true)
    // Submitting with no file sends nothing.
    button.closest('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    await user.upload(input, FILE)
    expect(button.disabled).toBe(false)
  })

  it('uploads the file and lists each triaged ticket with a link', async () => {
    const user = userEvent.setup()
    const api = mockApi(async () =>
      json({ filename: 'batch.md', records: [makeReplyRecord(), makeRecord({ ticket_id: 'e1' })] }),
    )
    const { queryClient } = renderLinked(<UploadPanel />)
    await user.upload(screen.getByLabelText('Ticket file'), FILE)
    await user.click(screen.getByRole('button', { name: 'Upload and triage' }))
    expect(await screen.findByText(/Triaged 2 ticket\(s\) from batch.md: 1 replied, 1 sent/)).toBeTruthy()
    const request = api.mock.calls[0][0]
    expect(new URL(request.url).pathname).toBe('/api/tickets/upload')
    expect(request.method).toBe('POST')
    // jsdom drops the file name in transit, so check the content.
    expect(await ((await request.formData()).get('file') as Blob).text()).toBe('Export\nHow?')
    expect(screen.getByRole('link', { name: /Refund please/ }).getAttribute('href')).toBe('/tickets/e1')
    expect(queryClient.isMutating()).toBe(0)
  })

  it('shows progress while uploading', async () => {
    const user = userEvent.setup()
    mockApi(() => new Promise<Response>(() => {}))
    renderLinked(<UploadPanel />)
    await user.upload(screen.getByLabelText('Ticket file'), FILE)
    await user.click(screen.getByRole('button', { name: 'Upload and triage' }))
    expect(await screen.findByRole('button', { name: 'Triaging…' })).toBeTruthy()
  })

  it('shows the reason a file was refused', async () => {
    const user = userEvent.setup()
    mockApi(async () => json({ detail: 'legacy .doc files are not supported' }, 422))
    renderLinked(<UploadPanel />)
    await user.upload(screen.getByLabelText('Ticket file'), FILE)
    await user.click(screen.getByRole('button', { name: 'Upload and triage' }))
    expect((await screen.findByRole('alert')).textContent).toBe('legacy .doc files are not supported')
  })

  it('clears the file when the picker is emptied', async () => {
    renderLinked(<UploadPanel />)
    const input = screen.getByLabelText('Ticket file') as HTMLInputElement
    await userEvent.upload(input, FILE)
    Object.defineProperty(input, 'files', { value: [], configurable: true })
    input.dispatchEvent(new Event('change', { bubbles: true }))
    await waitFor(() =>
      expect((screen.getByRole('button', { name: 'Upload and triage' }) as HTMLButtonElement).disabled).toBe(true),
    )
  })
})
