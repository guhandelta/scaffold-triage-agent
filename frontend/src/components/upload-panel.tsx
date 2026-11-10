import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { FileUp } from 'lucide-react'
import { type FormEvent, useState } from 'react'

import {
  escalationsQueryKey,
  listTicketsQueryKey,
  uploadTicketsMutation,
} from '@/client/@tanstack/react-query.gen'
import { StatusBadge } from '@/components/decision-badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { errorText } from '@/lib/tickets'

export const ACCEPTED = '.csv,.md,.markdown,.txt,.docx'

/** Triage a batch of tickets from a file, then list what the agent did with each. */
export function UploadPanel() {
  const queryClient = useQueryClient()
  const [file, setFile] = useState<File | null>(null)
  const upload = useMutation({
    ...uploadTicketsMutation(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: listTicketsQueryKey() })
      queryClient.invalidateQueries({ queryKey: escalationsQueryKey() })
    },
  })

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (file) upload.mutate({ body: { file } })
  }

  const records = upload.data?.records ?? []
  const replied = records.filter((r) => r.status === 'replied').length

  return (
    <Card className="shadow-sm">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <FileUp className="size-5 text-primary" aria-hidden /> Upload tickets
        </CardTitle>
        <CardDescription>
          A .csv with subject, body and email columns, or a .md, .txt or .docx file with tickets
          separated by a line of three dashes (---). Legacy .doc files need saving as .docx first.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <form onSubmit={onSubmit} className="flex flex-wrap items-center gap-3">
          <input
            aria-label="Ticket file"
            type="file"
            accept={ACCEPTED}
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="text-sm file:mr-3 file:rounded-md file:border file:bg-background file:px-3 file:py-1.5 file:text-sm"
          />
          <Button type="submit" disabled={!file || upload.isPending}>
            {upload.isPending ? 'Triaging…' : 'Upload and triage'}
          </Button>
        </form>
        {upload.isError && (
          <p role="alert" className="text-sm text-destructive">
            {errorText(upload.error, 'The upload failed.')}
          </p>
        )}
        {upload.data && (
          <div className="grid gap-2">
            <p className="text-sm">
              Triaged {records.length} ticket(s) from {upload.data.filename}: {replied} replied,{' '}
              {records.length - replied} sent to a person.
            </p>
            <ul className="grid gap-2">
              {records.map((record) => (
                <li key={record.ticket_id}>
                  <Link
                    to="/tickets/$ticketId"
                    params={{ ticketId: record.ticket_id }}
                    className="flex items-center justify-between gap-2 rounded-lg border px-3 py-2 text-sm hover:bg-muted"
                  >
                    <span className="truncate">{record.ticket.subject}</span>
                    <StatusBadge status={record.status} />
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
