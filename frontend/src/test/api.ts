import { vi } from 'vitest'

import { client } from '@/client/client.gen'

/** Route the generated client through a mock. The client sends a Request object. */
export function mockApi(handler: (request: Request) => Promise<Response>) {
  const mock = vi.fn(handler)
  client.setConfig({ fetch: mock as unknown as typeof fetch })
  return mock
}

export function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}
