import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { client } from '@/client/client.gen'
import { json, mockApi } from '@/test/api'
import { cleanName, DEFAULT_VIEWER, installViewerHeaders, loadViewer, saveViewer } from '@/lib/user'

const realFetch = client.getConfig().fetch
beforeEach(() => localStorage.clear())
afterEach(() => {
  client.setConfig({ fetch: realFetch })
  vi.restoreAllMocks()
})

describe('viewer storage', () => {
  it('defaults to the reviewer', () => {
    expect(loadViewer()).toEqual(DEFAULT_VIEWER)
  })

  it('saves and loads a cleaned viewer', () => {
    expect(saveViewer({ name: '  Sam  ', role: 'agent' })).toEqual({ name: 'Sam', role: 'agent' })
    expect(loadViewer()).toEqual({ name: 'Sam', role: 'agent' })
  })

  it('uses the default name when the name is blank', () => {
    expect(saveViewer({ name: '   ', role: 'viewer' })).toEqual({ name: 'Reviewer', role: 'viewer' })
  })

  it('ignores saved data with an unknown role, no name, or bad JSON', () => {
    localStorage.setItem('triage.viewer', JSON.stringify({ name: 'Sam', role: 'ceo' }))
    expect(loadViewer()).toEqual(DEFAULT_VIEWER)
    localStorage.setItem('triage.viewer', JSON.stringify({ role: 'agent' }))
    expect(loadViewer()).toEqual(DEFAULT_VIEWER)
    localStorage.setItem('triage.viewer', '{nope')
    expect(loadViewer()).toEqual(DEFAULT_VIEWER)
  })

  it('still works when storage is blocked', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    expect(saveViewer({ name: 'Sam', role: 'admin' })).toEqual({ name: 'Sam', role: 'admin' })
  })

  it('keeps names safe to send as a header', () => {
    expect(cleanName(' Zoë ✨ Lee ')).toBe('Zo  Lee')
    expect(cleanName('x'.repeat(100))).toHaveLength(80)
  })
})

describe('installViewerHeaders', () => {
  it('sends the current viewer with every request, once', async () => {
    installViewerHeaders()
    installViewerHeaders()
    saveViewer({ name: 'Sam', role: 'agent' })
    const api = mockApi(async () => json({ status: 'ok' }))
    await client.get({ url: '/api/health' })
    const request = api.mock.calls[0][0]
    expect(request.headers.get('X-User-Name')).toBe('Sam')
    expect(request.headers.get('X-User-Role')).toBe('agent')
  })
})
