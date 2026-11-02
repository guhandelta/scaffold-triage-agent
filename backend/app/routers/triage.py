import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.agent import get_chain
from app.agent.providers import FallbackChain
from app.memory import memory_for
from app.routing import Route, route_ticket
from app.schemas import Action, Decision, TicketIn, TriageResult

router = APIRouter(prefix="/api", tags=["triage"])

ChainDep = Annotated[FallbackChain, Depends(get_chain)]


@router.post("/triage", response_model=TriageResult)
async def triage(ticket: TicketIn, chain: ChainDep) -> TriageResult:
    """Route the ticket, then let the models decide, trying each in turn."""
    ticket_id = uuid.uuid4().hex[:12]
    memory = memory_for(ticket_id)

    route = route_ticket(ticket)
    memory.record("route", route=route.route.value, reason=route.reason)

    if route.route is Route.human:
        decision = Decision(
            action=Action.escalate,
            reasoning=f"Routed to a person by rule: {route.reason}.",
            reply_text=None,
        )
        memory.record("decision", provider="rules", action=decision.action.value)
        return TriageResult(
            decision=decision,
            route=route.route.value,
            provider="rules",
            failed_attempts=[],
            ticket_id=ticket_id,
        )

    decision, provider, errors = await chain.decide(ticket)
    for error in errors:
        memory.record("error", attempt=error)
    memory.record("decision", provider=provider, action=decision.action.value)
    return TriageResult(
        decision=decision,
        route=route.route.value,
        provider=provider,
        failed_attempts=errors,
        ticket_id=ticket_id,
    )
