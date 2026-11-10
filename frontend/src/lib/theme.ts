/**
 * Color themes, following the DSA chatbot's theme switcher.
 *
 * Five choices:
 *  - `auto`: the default light or dark look, following the device setting
 *  - four palettes, each with a fixed light or dark base:
 *      `calm` (light, teal), `energize` (light, orange), `focus` (dark, indigo), `warm` (dark, amber)
 *
 * A palette sets the `dark` class when its base is dark (so `dark:` styles apply), a
 * `data-palette` attribute, and its colors as inline custom properties on the document element,
 * which override the defaults in index.css. Auto clears them.
 *
 * The choice is kept in localStorage for this browser only. Anything unreadable falls back to auto.
 */

export type Palette = 'calm' | 'energize' | 'focus' | 'warm'
export type ThemeChoice = 'auto' | Palette

export const THEME_STORAGE_KEY = 'triage.theme'

/** The shadcn color variables a palette sets, without the leading `--`. */
export type PaletteTokens = Record<
  | 'background' | 'foreground' | 'card' | 'card-foreground' | 'popover' | 'popover-foreground'
  | 'primary' | 'primary-foreground' | 'secondary' | 'secondary-foreground' | 'muted'
  | 'muted-foreground' | 'accent' | 'accent-foreground' | 'border' | 'input' | 'ring',
  string
>

export type PaletteDefinition = {
  label: string
  description: string
  base: 'light' | 'dark'
  tokens: PaletteTokens
}

function palette(
  label: string,
  description: string,
  base: 'light' | 'dark',
  c: {
    bg: string
    surface: string
    text: string
    muted: string
    accent: string
    onAccent: string
    soft: string
    line: string
    input: string
    ring: string
  },
): PaletteDefinition {
  return {
    label,
    description,
    base,
    tokens: {
      background: c.bg,
      foreground: c.text,
      card: c.surface,
      'card-foreground': c.text,
      popover: c.surface,
      'popover-foreground': c.text,
      primary: c.accent,
      'primary-foreground': c.onAccent,
      secondary: c.soft,
      'secondary-foreground': c.text,
      muted: c.soft,
      'muted-foreground': c.muted,
      accent: c.soft,
      'accent-foreground': c.text,
      border: c.line,
      input: c.input,
      ring: c.ring,
    },
  }
}

/** The palettes, with the DSA chatbot's colors. Text pairs are checked for WCAG AA in theme.test.ts. */
export const PALETTES: Record<Palette, PaletteDefinition> = {
  calm: palette('Calm', 'Light, teal: a quiet, open background', 'light', {
    bg: '#dce6e3', surface: '#e8efec', text: '#182c29', muted: '#455c57',
    accent: '#245b56', onAccent: '#e8efec', soft: '#cdded8',
    line: '#cbd7d5', input: '#b9c9c5', ring: '#32766f',
  }),
  energize: palette('Energize', 'Light, orange: a brighter, lively background', 'light', {
    bg: '#e5ddd1', surface: '#efe8dd', text: '#2a1b16', muted: '#68544d',
    accent: '#914015', onAccent: '#efe8dd', soft: '#e4d5c2',
    line: '#dbcfc2', input: '#cbbca9', ring: '#7f3510',
  }),
  focus: palette('Focus', 'Dark, indigo: low glare for long sessions', 'dark', {
    bg: '#1b1f2a', surface: '#1e2433', text: '#e8ecf4', muted: '#b5bdcf',
    accent: '#8fa8ff', onAccent: '#1b1f2a', soft: '#2f374a',
    line: 'rgba(143, 168, 255, 0.2)', input: 'rgba(143, 168, 255, 0.3)', ring: '#a9bdff',
  }),
  warm: palette('Warm', 'Dark, amber: a soft, cozy background', 'dark', {
    bg: '#2a211b', surface: '#2f261f', text: '#f5ebdd', muted: '#d2bfa8',
    accent: '#e0b36b', onAccent: '#2a211b', soft: '#463a30',
    line: 'rgba(224, 179, 107, 0.2)', input: 'rgba(224, 179, 107, 0.3)', ring: '#f0cc8c',
  }),
}

export const PALETTE_NAMES = Object.keys(PALETTES) as Palette[]
const TOKEN_NAMES = Object.keys(PALETTES.calm.tokens) as (keyof PaletteTokens)[]

export function isThemeChoice(value: unknown): value is ThemeChoice {
  return value === 'auto' || (PALETTE_NAMES as unknown[]).includes(value)
}

export function readStoredChoice(): ThemeChoice {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY)
    return isThemeChoice(stored) ? stored : 'auto'
  } catch {
    return 'auto'
  }
}

export function writeStoredChoice(choice: ThemeChoice): void {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, choice)
  } catch {
    // The theme still applies for this visit; it just is not remembered.
  }
}

export function systemPrefersDark(): boolean {
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false
}

/** Apply a choice to the page, and return whether the result is dark. */
export function applyChoice(choice: ThemeChoice): boolean {
  const root = document.documentElement
  for (const name of TOKEN_NAMES) root.style.removeProperty(`--${name}`)
  root.removeAttribute('data-palette')

  let dark = systemPrefersDark()
  if (choice !== 'auto') {
    const definition = PALETTES[choice]
    dark = definition.base === 'dark'
    root.setAttribute('data-palette', choice)
    for (const name of TOKEN_NAMES) root.style.setProperty(`--${name}`, definition.tokens[name])
  }
  root.classList.toggle('dark', dark)
  root.style.colorScheme = dark ? 'dark' : 'light'
  return dark
}

/** Apply the stored choice. Call before the first render so the page never flashes. */
export function applyStoredChoice(): ThemeChoice {
  const choice = readStoredChoice()
  applyChoice(choice)
  return choice
}

function luminance(hex: string): number {
  const value = hex.replace('#', '')
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(value.slice(i, i + 2), 16) / 255)
  const linear = (c: number) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4)
  return 0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b)
}

/** WCAG contrast ratio between two #rrggbb colors, from 1 to 21. */
export function contrastRatio(a: string, b: string): number {
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (light + 0.05) / (dark + 0.05)
}
