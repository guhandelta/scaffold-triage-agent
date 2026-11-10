"""Offline triage rules, grounded in the support docs.

Used when no model key is set, so the whole app runs with no network. It replies only with the
text of the best-matching doc section and cites it. Anything else goes to a person.
"""

from collections.abc import Sequence

from app.org_config import OrgConfig
from app.schemas import Action, Decision, Source, TicketIn


def decide(
    ticket: TicketIn, sources: Sequence[Source] = (), config: OrgConfig | None = None
) -> Decision:
    """Reply with the best doc section, or escalate. Phrases and wording come from the config."""
    config = config or OrgConfig()
    text = f"{ticket.subject} {ticket.body}".lower()
    for word in config.routing.human_only:
        if word in text:
            return Decision(
                action=Action.escalate,
                reasoning=f"Mentions '{word}', which needs a person.",
            )

    answerable = [s for s in sources if not s.policy]
    if not answerable:
        return Decision(
            action=Action.escalate,
            reasoning="No support doc covers this, so a person should answer it.",
        )

    best = answerable[0]
    where = f"{best.title} / {best.heading}"
    if best.human_only:
        return Decision(
            action=Action.escalate,
            reasoning=f'The docs say a person handles this ("{where}").',
            citations=[best.id],
        )
    if best.score < config.agent.min_score:
        return Decision(
            action=Action.escalate,
            reasoning=f'The closest doc ("{where}") is a weak match, so a person should check.',
        )
    return Decision(
        action=Action.reply,
        reasoning=f'Answered from "{where}".',
        reply_text="\n\n".join(
            part
            for part in (config.replies.greeting.strip(), best.text, config.replies.closing.strip())
            if part
        ),
        citations=[best.id],
    )
