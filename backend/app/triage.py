"""Offline triage rules, grounded in the support docs.

Used when no model key is set, so the whole app runs with no network. It replies only with the
text of the best-matching doc section and cites it. Anything else goes to a person.
"""

from collections.abc import Sequence

from app.schemas import Action, Decision, Source, TicketIn

ESCALATE_WORDS = ("refund", "charged twice", "legal", "lawyer", "fraud", "hacked", "outage")

# Below this BM25 score the best section is too weak a match to send as an answer.
MIN_SCORE = 2.5


def decide(ticket: TicketIn, sources: Sequence[Source] = ()) -> Decision:
    text = f"{ticket.subject} {ticket.body}".lower()
    for word in ESCALATE_WORDS:
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
    if best.score < MIN_SCORE:
        return Decision(
            action=Action.escalate,
            reasoning=f'The closest doc ("{where}") is a weak match, so a person should check.',
        )
    return Decision(
        action=Action.reply,
        reasoning=f'Answered from "{where}".',
        reply_text=(
            f"Hi,\n\n{best.text}\n\n"
            "If this does not solve it, reply here and a person on our team will take a look."
        ),
        citations=[best.id],
    )
