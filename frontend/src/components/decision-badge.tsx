import type { Action } from '@/client'
import { Badge } from '@/components/ui/badge'

export function DecisionBadge({ action }: { action: Action }) {
  if (action === 'escalate') {
    return <Badge className="bg-amber-100 text-amber-900 hover:bg-amber-100">Escalated</Badge>
  }
  return <Badge className="bg-emerald-100 text-emerald-900 hover:bg-emerald-100">Replied</Badge>
}
