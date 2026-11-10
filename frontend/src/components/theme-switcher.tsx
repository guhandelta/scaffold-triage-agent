import { Flame, Leaf, SunMoon, Target, Zap, type LucideIcon } from 'lucide-react'
import { useEffect, useState } from 'react'

import { applyChoice, PALETTES, readStoredChoice, type ThemeChoice, writeStoredChoice } from '@/lib/theme'

type ThemeOption = { choice: ThemeChoice; name: string; description: string; icon: LucideIcon }

/** Auto first, then the four palettes. Names and descriptions come from PALETTES. */
export const THEME_OPTIONS: readonly ThemeOption[] = [
  { choice: 'auto', name: 'Auto', description: 'Follows your device setting', icon: SunMoon },
  { choice: 'calm', name: PALETTES.calm.label, description: PALETTES.calm.description, icon: Leaf },
  { choice: 'energize', name: PALETTES.energize.label, description: PALETTES.energize.description, icon: Zap },
  { choice: 'focus', name: PALETTES.focus.label, description: PALETTES.focus.description, icon: Target },
  { choice: 'warm', name: PALETTES.warm.label, description: PALETTES.warm.description, icon: Flame },
]

/** The header's theme control: one icon button per theme, with the current one pressed. */
export function ThemeSwitcher() {
  const [choice, setChoice] = useState<ThemeChoice>(readStoredChoice)

  // In auto, follow live changes to the device's light or dark setting.
  useEffect(() => {
    if (choice !== 'auto' || !window.matchMedia) return
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = () => applyChoice('auto')
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [choice])

  function choose(next: ThemeChoice) {
    setChoice(next)
    applyChoice(next)
    writeStoredChoice(next)
  }

  return (
    <div
      role="group"
      aria-label="Color theme"
      className="inline-flex items-center gap-0.5 rounded-full border bg-card p-0.5"
    >
      {THEME_OPTIONS.map(({ choice: value, name, description, icon: Icon }) => (
        <button
          key={value}
          type="button"
          aria-pressed={choice === value}
          aria-label={`${name} theme: ${description}`}
          title={name}
          onClick={() => choose(value)}
          className="grid size-7 place-items-center rounded-full text-muted-foreground transition hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring aria-pressed:bg-primary aria-pressed:text-primary-foreground"
        >
          <Icon className="size-4" aria-hidden />
        </button>
      ))}
    </div>
  )
}
