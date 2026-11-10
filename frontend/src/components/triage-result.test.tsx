import { fireEvent, screen } from '@testing-library/react'
import { renderLinked } from '@/test/render-linked'
import { describe, expect, it, vi } from 'vitest'

import type { TriageResult } from '@/client'
import { EXPORT_SOURCE, POLICY_SOURCE } from '@/components/test-data'
import { TriageResultPanel } from '@/components/triage-result'

function result(overrides: Partial<TriageResult['decision']> = {}, extra: Partial<TriageResult> = {}) {
  return {
    decision: { action: 'reply', reasoning: 'Docs cover it.', reply_text: 'Use Export.', ...overrides },
    route: 'agent',
    provider: 'claude',
    failed_attempts: [],
    ticket_id: 't1',
    ...extra,
  } as TriageResult
}

describe('TriageResultPanel', () => {
  it('shows the reasoning, the decider and the suggested reply', () => {
    renderLinked(<TriageResultPanel result={result()} />)
    expect(screen.getByText('Docs cover it.')).toBeTruthy()
    expect(screen.getByText(/decided by claude/)).toBeTruthy()
    expect(screen.getByText('Use Export.')).toBeTruthy()
    expect(screen.getByText('Replied')).toBeTruthy()
  })

  it('tells the user a person must act on an escalation, with no reply', () => {
    renderLinked(
      <TriageResultPanel
        result={result({ action: 'escalate', reply_text: null, reasoning: 'Refund.' })}
      />,
    )
    expect(screen.getByText('Escalated')).toBeTruthy()
    expect(screen.getByText(/A person needs to handle this one/)).toBeTruthy()
    expect(screen.queryByText('Suggested reply')).toBeNull()
  })

  it('lists the failed attempts that were skipped', () => {
    renderLinked(
      <TriageResultPanel
        result={result({}, { failed_attempts: ['claude: 429', 'openai: 401'] })}
      />,
    )
    expect(screen.getByText(/Fell back past 2 failed attempt/)).toBeTruthy()
    expect(screen.getByText('claude: 429')).toBeTruthy()
    expect(screen.getByText('openai: 401')).toBeTruthy()
  })

  it('copies the reply and then shows Copied', async () => {
    const writeText = vi.fn(async () => undefined)
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    renderLinked(<TriageResultPanel result={result()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Copy' }))
    expect(writeText).toHaveBeenCalledWith('Use Export.')
    expect(await screen.findByRole('button', { name: 'Copied' })).toBeTruthy()
    vi.unstubAllGlobals()
  })

  it('keeps the Copy label when the clipboard refuses', async () => {
    vi.stubGlobal('navigator', { clipboard: { writeText: vi.fn(async () => Promise.reject(new Error('no'))) } })
    renderLinked(<TriageResultPanel result={result()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Copy' }))
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(screen.getByRole('button', { name: 'Copy' })).toBeTruthy()
    vi.unstubAllGlobals()
  })
})

describe('TriageResultPanel sources', () => {
  it('links to the ticket and lists the cited source first', () => {
    renderLinked(
      <TriageResultPanel
        result={result(
          { citations: [EXPORT_SOURCE.id] },
          { sources: [POLICY_SOURCE, EXPORT_SOURCE] },
        )}
      />,
    )
    expect(screen.getByRole('link', { name: /Open ticket/ }).getAttribute('href')).toBe('/tickets/t1')
    const items = screen.getAllByRole('listitem')
    expect(items[0].textContent).toContain('Export your data')
    expect(items[0].textContent).toContain('Cited')
    expect(items[1].textContent).toContain('Agent policy')
  })

  it('says when no doc matched, even for an old result with no sources', () => {
    renderLinked(<TriageResultPanel result={result({ citations: undefined })} />)
    expect(screen.getByText(/No support doc matched/)).toBeTruthy()
  })
})
