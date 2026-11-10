"""Live check: send one sample ticket to each model that has a key, and print the result.

Run from backend/: uv run python scripts/live_check.py
Prints one line per provider with the action and the reply text. Exits 1 if any keyed
provider fails, so it can gate a deploy. Keys are redacted from any error text.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent.providers import ClaudeProvider, GoogleProvider, OpenAIProvider
from app.config import get_settings
from app.kb import get_kb
from app.schemas import TicketIn

TICKET = TicketIn(subject="How do I export my data to CSV?", body="Where is the export button?")


async def main() -> int:
    s = get_settings()
    secrets = [k for k in (s.anthropic_api_key, s.openai_api_key, s.google_api_key) if k]
    checks = [
        (
            "claude",
            s.anthropic_api_key,
            lambda: ClaudeProvider(s.anthropic_api_key, s.claude_model),
        ),
        ("openai", s.openai_api_key, lambda: OpenAIProvider(s.openai_api_key, s.openai_model)),
        ("google", s.google_api_key, lambda: GoogleProvider(s.google_api_key, s.google_model)),
    ]
    sources = get_kb().search(f"{TICKET.subject}\n{TICKET.body}")
    print(f"docs: {len(sources)} section(s) retrieved")
    failed = 0
    for name, key, make in checks:
        if not key:
            print(f"{name}: no key set, skipped")
            continue
        try:
            decision = await make().decide(TICKET, sources)
            print(f"{name}: OK action={decision.action.value}")
            print(f"  reasoning: {decision.reasoning}")
            print(f"  reply_text: {decision.reply_text or '(none)'}")
            print(f"  citations: {', '.join(decision.citations) or '(none)'}")
        except Exception as e:
            failed += 1
            message = str(e)
            for secret in secrets:
                message = message.replace(secret, "***")
            print(f"{name}: FAILED {type(e).__name__}: {message[:200]}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
