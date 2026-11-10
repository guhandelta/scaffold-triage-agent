"""The triage pipeline: route, retrieve docs, decide, check grounding, save with history."""

import uuid
from collections.abc import Sequence

from app.agent.providers import FallbackChain
from app.kb import KnowledgeBase
from app.routing import Route, route_ticket
from app.schemas import (
    Action,
    Decision,
    HistoryEvent,
    Source,
    TicketIn,
    TicketRecord,
    TicketStatus,
    TriageResult,
)
from app.store import TicketStore


def status_for(decision: Decision) -> TicketStatus:
    return TicketStatus.replied if decision.action == Action.reply else TicketStatus.escalated


def ground(decision: Decision, sources: Sequence[Source]) -> tuple[Decision, str | None]:
    """Keep only citations to sections the agent was given, and refuse ungrounded replies.

    A reply must cite at least one non-policy section, and none marked as handled by a person.
    Otherwise it becomes an escalation. Returns the checked decision and a note when it changed.
    """
    by_id = {s.id: s for s in sources}
    cited = [c for c in dict.fromkeys(decision.citations) if c in by_id]
    dropped = len(decision.citations) - len(cited)
    checked = decision.model_copy(update={"citations": cited})
    if decision.action == Action.escalate:
        return checked, (f"Dropped {dropped} unknown citation(s)." if dropped else None)

    human_only = [c for c in cited if by_id[c].human_only]
    if human_only:
        return (
            Decision(
                action=Action.escalate,
                reasoning="The reply relied on a doc section that a person must handle.",
                citations=human_only,
            ),
            "Reply cited a section marked as handled by a person, so it was escalated.",
        )
    if not any(not by_id[c].policy for c in cited):
        return (
            Decision(
                action=Action.escalate,
                reasoning="The reply was not backed by any support doc, so a person should check.",
                citations=cited,
            ),
            "Reply cited no support doc, so it was escalated instead of sent.",
        )
    return checked, (f"Dropped {dropped} unknown citation(s)." if dropped else None)


def _event(kind: str, detail: str, actor: str) -> HistoryEvent:
    return HistoryEvent(kind=kind, detail=detail, actor=actor)


async def run_triage(
    ticket: TicketIn, chain: FallbackChain, store: TicketStore, kb: KnowledgeBase
) -> TicketRecord:
    ticket_id = uuid.uuid4().hex[:12]
    history = [_event("received", f"Subject: {ticket.subject}", "system")]

    route = route_ticket(ticket)
    history.append(_event("routed", f"{route.route.value}: {route.reason}", "rules"))

    sources = kb.search(f"{ticket.subject}\n{ticket.body}")
    titles = "; ".join(f"{s.title} / {s.heading}" for s in sources) or "nothing matched"
    history.append(_event("retrieved", f"Read {len(sources)} doc section(s): {titles}", "agent"))

    if route.route is Route.human:
        decision = Decision(
            action=Action.escalate, reasoning=f"Routed to a person by rule: {route.reason}."
        )
        provider, errors = "rules", []
    else:
        decision, provider, errors = await chain.decide(ticket, sources)
        for error in errors:
            history.append(_event("error", error, "agent"))

    decision, note = ground(decision, sources)
    if note:
        history.append(_event("grounding", note, "agent"))
    cites = f", citing {len(decision.citations)} section(s)" if decision.citations else ""
    history.append(_event("decided", f"{decision.action.value} by {provider}{cites}", provider))

    result = TriageResult(
        decision=decision,
        route=route.route.value,
        provider=provider,
        failed_attempts=errors,
        ticket_id=ticket_id,
        sources=sources,
    )
    record = TicketRecord(
        ticket_id=ticket_id,
        ticket=ticket,
        result=result,
        status=status_for(decision),
        history=history,
    )
    return store.save(record)
