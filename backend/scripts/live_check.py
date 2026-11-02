"""Live check: send one sample ticket to each model that has a key, and print the result.

Run from backend/: uv run python scripts/live_check.py
Prints a status per provider. Keys are redacted from any error text.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent.providers import ClaudeProvider, GoogleProvider, OpenAIProvider
from app.config import get_settings
from app.schemas import TicketIn

TICKET = TicketIn(subject="How do I export my data to CSV?", body="Where is the export button?")


async def main() -> None:
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
    for name, key, make in checks:
        if not key:
            print(f"{name}: no key set, skipped")
            continue
        try:
            decision = await make().decide(TICKET)
            print(f"{name}: OK action={decision.action.value}")
        except Exception as e:
            message = str(e)
            for secret in secrets:
                message = message.replace(secret, "***")
            print(f"{name}: FAILED {type(e).__name__}: {message[:200]}")


asyncio.run(main())
