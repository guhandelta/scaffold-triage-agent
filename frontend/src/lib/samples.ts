export type SampleTicket = {
  label: string
  subject: string
  body: string
}

/** One-click examples so a reviewer can try the agent without typing a ticket. */
export const SAMPLE_TICKETS: SampleTicket[] = [
  {
    label: 'Simple question',
    subject: 'How do I export my data to CSV?',
    body: 'Where is the export button?',
  },
  {
    label: 'Refund request',
    subject: 'Refund please',
    body: 'I was charged twice this month and I want my money back.',
  },
  {
    label: 'Outage report',
    subject: 'Dashboard is down',
    body: 'The whole dashboard is down for our team since 9am.',
  },
]
