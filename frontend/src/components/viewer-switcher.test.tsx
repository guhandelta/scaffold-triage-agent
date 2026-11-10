import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ViewerSwitcher } from '@/components/viewer-switcher'
import { loadViewer } from '@/lib/user'
import { renderLinked } from '@/test/render-linked'

beforeEach(() => localStorage.clear())
afterEach(() => vi.restoreAllMocks())

describe('ViewerSwitcher', () => {
  it('starts as the default reviewer', () => {
    renderLinked(<ViewerSwitcher />)
    expect((screen.getByLabelText('Your name') as HTMLInputElement).value).toBe('Reviewer')
    expect((screen.getByLabelText('Your role') as HTMLSelectElement).value).toBe('reviewer')
  })

  it('switches role, saves it, and refetches what the page shows', async () => {
    const user = userEvent.setup()
    const { queryClient } = renderLinked(<ViewerSwitcher />)
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries')
    await user.selectOptions(screen.getByLabelText('Your role'), 'viewer')
    expect(loadViewer().role).toBe('viewer')
    expect(invalidate).toHaveBeenCalled()
  })

  it('saves a new name on Enter, cleaned, and skips a blur with no change', async () => {
    const user = userEvent.setup()
    const { queryClient } = renderLinked(<ViewerSwitcher />)
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries')
    const name = screen.getByLabelText('Your name') as HTMLInputElement
    await user.click(name)
    await user.tab()
    expect(invalidate).not.toHaveBeenCalled()
    await user.clear(name)
    await user.type(name, '  Sam {Enter}')
    await waitFor(() => expect(loadViewer().name).toBe('Sam'))
    expect(name.value).toBe('Sam')
    await user.type(name, 'x')
    await user.keyboard('{Shift}')
    expect(loadViewer().name).toBe('Sam')
  })
})
