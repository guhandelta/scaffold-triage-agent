"""The triage step. Phase 0 uses simple rules so the whole path runs with no model.

Later phases swap in a model-backed agent behind the same `decide` function.
"""

from app.schemas import Action, Decision, TicketIn

ESCALATE_WORDS = ("refund", "charged twice", "legal", "lawyer", "fraud", "hacked", "outage")


def decide(ticket: TicketIn) -> Decision:
    text = f"{ticket.subject} {ticket.body}".lower()
    for word in ESCALATE_WORDS:
        if word in text:
            return Decision(
                action=Action.escalate,
                reasoning=f"Mentions '{word}', which needs a person.",
            )
    return Decision(
        action=Action.reply,
        reasoning="No escalation signals found.",
        reply_text="Thanks for reaching out. We are looking into this and will follow up.",
    )
