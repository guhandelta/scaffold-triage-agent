import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'

import type { Action, Permission, TicketRecord } from '@/client'
import {
  addNoteMutation,
  assignMutation,
  confirmMutation,
  escalationsQueryKey,
  getTicketQueryKey,
  listTicketsQueryKey,
  overrideMutation,
  resolveMutation,
} from '@/client/@tanstack/react-query.gen'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { errorText } from '@/lib/tickets'

type Props = {
  record: TicketRecord
  permissions: Permission[]
  role: string
}

/** What a person can do to a ticket. Each control shows only when the role allows it. */
export function ReviewPanel({ record, permissions, role }: Props) {
  const queryClient = useQueryClient()
  const path = { ticket_id: record.ticket_id }
  const can = (p: Permission) => permissions.includes(p)
  const open = record.status !== 'resolved'

  function onSuccess(updated: TicketRecord) {
    queryClient.setQueryData(getTicketQueryKey({ path }), updated)
    queryClient.invalidateQueries({ queryKey: listTicketsQueryKey() })
    queryClient.invalidateQueries({ queryKey: escalationsQueryKey() })
  }

  const assign = useMutation({ ...assignMutation(), onSuccess })
  const note = useMutation({ ...addNoteMutation(), onSuccess })
  const confirm = useMutation({ ...confirmMutation(), onSuccess })
  const override = useMutation({ ...overrideMutation(), onSuccess })
  const resolve = useMutation({ ...resolveMutation(), onSuccess })
  const all = [assign, note, confirm, override, resolve]
  const busy = all.some((m) => m.isPending)
  const failed = all.find((m) => m.isError)

  if (permissions.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Your role ({role}) can view tickets but not change them.
      </p>
    )
  }

  return (
    <div className="grid gap-5">
      {failed && (
        <p role="alert" className="text-sm text-destructive">
          {errorText(failed.error, 'That change did not save.')}
        </p>
      )}

      {open && (can('confirm') || can('resolve')) && (
        <div className="flex flex-wrap gap-2">
          {can('confirm') && (
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() => confirm.mutate({ path })}
            >
              Confirm {record.decision.action === 'reply' ? 'reply' : 'escalation'}
            </Button>
          )}
          {can('resolve') && (
            <Button variant="outline" disabled={busy} onClick={() => resolve.mutate({ path })}>
              Mark resolved
            </Button>
          )}
        </div>
      )}
      {record.confirmed_by && (
        <p className="text-xs text-muted-foreground">Confirmed by {record.confirmed_by}</p>
      )}

      {open && can('override') && (
        <OverrideForm
          record={record}
          busy={busy}
          onSubmit={(body) => override.mutate({ path, body })}
        />
      )}

      {can('assign') && (
        <SingleField
          id="owner"
          label="Owner"
          placeholder="Name of the person handling it"
          initial={record.owner ?? ''}
          button="Assign"
          busy={busy}
          maxLength={80}
          onSubmit={(owner) => assign.mutate({ path, body: { owner } })}
        />
      )}

      {can('note') && (
        <SingleField
          id="note"
          label="Add a note"
          placeholder="Visible to the team, never to the customer"
          initial=""
          button="Add note"
          busy={busy}
          maxLength={2000}
          multiline
          onSubmit={(text) => note.mutate({ path, body: { text } })}
        />
      )}
    </div>
  )
}

type OverrideBody = { action: Action; reason: string; reply_text: string | null }

function OverrideForm({
  record,
  busy,
  onSubmit,
}: {
  record: TicketRecord
  busy: boolean
  onSubmit: (body: OverrideBody) => void
}) {
  const current = record.decision.action
  const [shown, setShown] = useState(false)
  const [action, setAction] = useState<Action>(current === 'reply' ? 'escalate' : 'reply')
  const [reason, setReason] = useState('')
  const [reply, setReply] = useState(record.decision.reply_text ?? '')

  if (!shown) {
    return (
      <Button variant="outline" className="justify-self-start" onClick={() => setShown(true)}>
        Override decision
      </Button>
    )
  }

  const ready = reason.trim() !== '' && (action === 'escalate' || reply.trim() !== '')

  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    onSubmit({
      action,
      reason: reason.trim(),
      reply_text: action === 'reply' ? reply.trim() : null,
    })
  }

  return (
    <form onSubmit={submit} className="grid gap-3 rounded-lg border p-4" aria-label="Override">
      <fieldset className="flex gap-4 text-sm">
        <legend className="mb-2 text-sm font-medium">Change the decision to</legend>
        {(['reply', 'escalate'] as const).map((value) => (
          <label key={value} className="flex items-center gap-2">
            <input
              type="radio"
              name="override-action"
              value={value}
              checked={action === value}
              onChange={() => setAction(value)}
            />
            {value === 'reply' ? 'Send a reply' : 'Hand to a person'}
          </label>
        ))}
      </fieldset>
      {action === 'reply' && (
        <div className="grid gap-2">
          <Label htmlFor="override-reply">Reply to the customer</Label>
          <Textarea
            id="override-reply"
            rows={5}
            value={reply}
            onChange={(e) => setReply(e.target.value)}
          />
        </div>
      )}
      <div className="grid gap-2">
        <Label htmlFor="override-reason">Reason</Label>
        <Input
          id="override-reason"
          value={reason}
          maxLength={1000}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Why the agent's call was wrong"
        />
      </div>
      <div className="flex gap-2">
        <Button type="submit" disabled={busy || !ready}>
          Save override
        </Button>
        <Button type="button" variant="ghost" onClick={() => setShown(false)}>
          Cancel
        </Button>
      </div>
    </form>
  )
}

function SingleField({
  id,
  label,
  placeholder,
  initial,
  button,
  busy,
  maxLength,
  multiline = false,
  onSubmit,
}: {
  id: string
  label: string
  placeholder: string
  initial: string
  button: string
  busy: boolean
  maxLength: number
  multiline?: boolean
  onSubmit: (value: string) => void
}) {
  const [value, setValue] = useState(initial)

  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    onSubmit(value.trim())
    if (multiline) setValue('')
  }

  const props = {
    id,
    value,
    placeholder,
    maxLength,
    onChange: (e: { target: { value: string } }) => setValue(e.target.value),
  }
  return (
    <form onSubmit={submit} className="grid gap-2">
      <Label htmlFor={id}>{label}</Label>
      {multiline ? <Textarea rows={3} {...props} /> : <Input {...props} />}
      <Button
        type="submit"
        variant="secondary"
        className="justify-self-start"
        disabled={busy || value.trim() === ''}
      >
        {button}
      </Button>
    </form>
  )
}
