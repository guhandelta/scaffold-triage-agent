import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { THEME_OPTIONS, ThemeSwitcher } from '@/components/theme-switcher'
import { applyChoice, readStoredChoice, writeStoredChoice } from '@/lib/theme'

type Listener = () => void

function mockMedia(dark: boolean) {
  const listeners = new Set<Listener>()
  const media = {
    matches: dark,
    addEventListener: vi.fn((_: string, fn: Listener) => listeners.add(fn)),
    removeEventListener: vi.fn((_: string, fn: Listener) => listeners.delete(fn)),
  }
  vi.stubGlobal('matchMedia', vi.fn(() => media))
  return { media, listeners }
}

beforeEach(() => localStorage.clear())
afterEach(() => {
  vi.unstubAllGlobals()
  applyChoice('auto')
})

describe('ThemeSwitcher', () => {
  it('offers auto and the four palettes, with auto pressed by default', () => {
    render(<ThemeSwitcher />)
    const buttons = screen.getAllByRole('button')
    expect(buttons.map((b) => b.getAttribute('title'))).toEqual(THEME_OPTIONS.map((o) => o.name))
    expect(buttons[0].getAttribute('aria-pressed')).toBe('true')
    expect(screen.getByRole('button', { name: /Focus theme: Dark, indigo/ })).toBeTruthy()
  })

  it('starts on the saved choice', () => {
    writeStoredChoice('warm')
    render(<ThemeSwitcher />)
    expect(screen.getByTitle('Warm').getAttribute('aria-pressed')).toBe('true')
  })

  it('applies and saves a new choice', async () => {
    const user = userEvent.setup()
    render(<ThemeSwitcher />)
    await user.click(screen.getByTitle('Focus'))
    expect(document.documentElement.dataset.palette).toBe('focus')
    expect(readStoredChoice()).toBe('focus')
    expect(screen.getByTitle('Focus').getAttribute('aria-pressed')).toBe('true')
    expect(screen.getByTitle('Auto').getAttribute('aria-pressed')).toBe('false')
  })

  it('follows the device setting only while on auto', async () => {
    const user = userEvent.setup()
    const { media, listeners } = mockMedia(false)
    render(<ThemeSwitcher />)
    expect(listeners.size).toBe(1)
    media.matches = true
    listeners.forEach((fn) => fn())
    expect(document.documentElement.classList.contains('dark')).toBe(true)
    await user.click(screen.getByTitle('Calm'))
    expect(listeners.size).toBe(0)
  })

  it('works in a browser without matchMedia', () => {
    vi.stubGlobal('matchMedia', undefined)
    render(<ThemeSwitcher />)
    expect(screen.getByTitle('Auto').getAttribute('aria-pressed')).toBe('true')
  })
})
