import { screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { client } from '@/client/client.gen'
import { json, mockApi } from '@/test/api'
import { renderShell } from '@/test/render-shell'

const realFetch = client.getConfig().fetch
afterEach(() => client.setConfig({ fetch: realFetch }))

describe('navigation in the shell', () => {
  it('links to the three pages', async () => {
    mockApi(async () => json({ status: 'ok', agent: 'rules' }))
    renderShell('/')
    expect(await screen.findByText('page /')).toBeTruthy()
    const nav = screen.getByRole('navigation', { name: 'Main' })
    expect(nav.querySelector('a[href="/tickets"]')?.textContent).toBe('Tickets')
    expect(nav.querySelector('a[href="/escalations"]')?.textContent).toBe('Escalations')
  })

  it('marks the active page in the nav', async () => {
    mockApi(async () => json({ status: 'ok', agent: 'rules' }))
    renderShell('/tickets')
    expect(await screen.findByText('page /tickets')).toBeTruthy()
    const active = screen.getByRole('navigation', { name: 'Main' }).querySelector('a[href="/tickets"]')
    expect(active?.className).toContain('font-medium')
  })
})

describe('API health badge', () => {
  it('shows the agent in use when the API is up', async () => {
    mockApi(async () => json({ status: 'ok', agent: 'rules' }))
    renderShell('/')
    expect(await screen.findByText(/API ok · rules/)).toBeTruthy()
  })

  it('warns when the API is offline', async () => {
    mockApi(async () => json({ detail: 'down' }, 500))
    renderShell('/')
    expect(await screen.findByText('API offline')).toBeTruthy()
  })

  it('shows nothing while the health check is still running', async () => {
    mockApi(() => new Promise<Response>(() => {}))
    renderShell('/')
    expect(screen.queryByText(/API ok/)).toBeNull()
    expect(screen.queryByText('API offline')).toBeNull()
  })
})
