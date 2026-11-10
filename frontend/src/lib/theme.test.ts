import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  applyChoice,
  applyStoredChoice,
  contrastRatio,
  PALETTE_NAMES,
  PALETTES,
  readStoredChoice,
  systemPrefersDark,
  THEME_STORAGE_KEY,
  writeStoredChoice,
} from '@/lib/theme'

const root = document.documentElement

function mockSystemDark(dark: boolean) {
  vi.stubGlobal(
    'matchMedia',
    vi.fn(() => ({ matches: dark, addEventListener: vi.fn(), removeEventListener: vi.fn() })),
  )
}

beforeEach(() => localStorage.clear())
afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  applyChoice('auto')
})

describe('palettes', () => {
  it('has four palettes with every color set', () => {
    expect(PALETTE_NAMES).toEqual(['calm', 'energize', 'focus', 'warm'])
    for (const name of PALETTE_NAMES) {
      expect(Object.keys(PALETTES[name].tokens)).toHaveLength(17)
    }
  })

  it.each(PALETTE_NAMES)('%s meets WCAG AA for text', (name) => {
    const t = PALETTES[name].tokens
    expect(contrastRatio(t.foreground, t.background)).toBeGreaterThanOrEqual(4.5)
    expect(contrastRatio(t['card-foreground'], t.card)).toBeGreaterThanOrEqual(4.5)
    expect(contrastRatio(t['muted-foreground'], t.card)).toBeGreaterThanOrEqual(4.5)
    expect(contrastRatio(t['muted-foreground'], t.muted)).toBeGreaterThanOrEqual(4.5)
    expect(contrastRatio(t['primary-foreground'], t.primary)).toBeGreaterThanOrEqual(4.5)
    expect(contrastRatio(t['secondary-foreground'], t.secondary)).toBeGreaterThanOrEqual(4.5)
  })

  it('computes contrast both ways round', () => {
    expect(contrastRatio('#000000', '#ffffff')).toBeCloseTo(21)
    expect(contrastRatio('#ffffff', '#000000')).toBeCloseTo(21)
  })
})

describe('storage', () => {
  it('defaults to auto, and ignores unknown values', () => {
    expect(readStoredChoice()).toBe('auto')
    localStorage.setItem(THEME_STORAGE_KEY, 'neon')
    expect(readStoredChoice()).toBe('auto')
  })

  it('saves and reads a choice', () => {
    writeStoredChoice('warm')
    expect(readStoredChoice()).toBe('warm')
  })

  it('falls back quietly when storage is blocked', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    expect(readStoredChoice()).toBe('auto')
    expect(() => writeStoredChoice('calm')).not.toThrow()
  })
})

describe('applying a theme', () => {
  it('sets a dark palette, its colors and the dark class', () => {
    expect(applyChoice('focus')).toBe(true)
    expect(root.dataset.palette).toBe('focus')
    expect(root.classList.contains('dark')).toBe(true)
    expect(root.style.getPropertyValue('--primary')).toBe('#8fa8ff')
    expect(root.style.colorScheme).toBe('dark')
  })

  it('sets a light palette without the dark class', () => {
    mockSystemDark(true)
    expect(applyChoice('energize')).toBe(false)
    expect(root.classList.contains('dark')).toBe(false)
    expect(root.style.getPropertyValue('--background')).toBe('#e5ddd1')
  })

  it('auto clears the palette and follows the device', () => {
    applyChoice('warm')
    mockSystemDark(true)
    expect(applyChoice('auto')).toBe(true)
    expect(root.dataset.palette).toBeUndefined()
    expect(root.style.getPropertyValue('--primary')).toBe('')
    mockSystemDark(false)
    expect(applyChoice('auto')).toBe(false)
    expect(root.style.colorScheme).toBe('light')
  })

  it('treats a browser without matchMedia as light', () => {
    vi.stubGlobal('matchMedia', undefined)
    expect(systemPrefersDark()).toBe(false)
  })

  it('applies the stored choice at startup', () => {
    writeStoredChoice('calm')
    expect(applyStoredChoice()).toBe('calm')
    expect(root.dataset.palette).toBe('calm')
  })
})
