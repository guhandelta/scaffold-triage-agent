import asyncio
from types import SimpleNamespace as NS

from app.agent.providers import ClaudeProvider, GoogleProvider, OpenAIProvider
from app.schemas import TicketIn

TICKET = TicketIn(subject="Export", body="Where is export?")
ANSWER = '{"action": "reply", "reasoning": "ok", "reply_text": "Use Export."}'


class Recorder:
    def __init__(self, reply):
        self.reply = reply
        self.kwargs = None

    async def create(self, **kwargs):
        self.kwargs = kwargs
        return self.reply


def _claude(p, rec):
    p.client = NS(messages=rec)
    return NS(stop_reason="end_turn", content=[NS(type="text", text=ANSWER)])


def test_claude_runs_at_low_effort():
    p = ClaudeProvider("k", "claude-opus-5-5")
    rec = Recorder(None)
    rec.reply = _claude(p, rec)
    asyncio.run(p.decide(TICKET))
    assert rec.kwargs["output_config"] == {"effort": "low"}


def test_openai_runs_at_low_effort():
    p = OpenAIProvider("k", "gpt-5")
    rec = Recorder(NS(choices=[NS(message=NS(content=ANSWER))]))
    p.client = NS(chat=NS(completions=rec))
    asyncio.run(p.decide(TICKET))
    assert rec.kwargs["reasoning_effort"] == "low"


def test_google_runs_at_low_effort():
    p = GoogleProvider("k", "gemini-2.5-pro")

    class Models:
        kwargs = None

        async def generate_content(self, **kwargs):
            Models.kwargs = kwargs
            return NS(text=ANSWER)

    p.client = NS(aio=NS(models=Models()))
    asyncio.run(p.decide(TICKET))
    assert Models.kwargs["config"]["thinking_config"] == {"thinking_level": "low"}
