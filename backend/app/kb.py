"""Support docs and retrieval.

Docs live in one folder per product area, one Markdown file per topic. Each `## Section` is a
retrievable unit with a stable id, so the agent can cite exactly what it used. A section that
starts with `> Handled by a person.` must never be answered by the agent.

Retrieval is BM25 over words. It needs no model and no network, and it is easy to swap for
embeddings later because callers only see `search()`.
"""

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from app.config import get_settings
from app.org_config import get_org_config
from app.schemas import Source

HUMAN_MARKER = "> handled by a person"
POLICY_AREA = "policies"

_WORD = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    """a an and are as at be by can do does for from has have how i if in into is it its my
    of on or our so that the their them then there this to up was we what when where which who
    why will with you your me please hi hello thanks thank""".split()
)


def _stem(word: str) -> str:
    """Fold simple plurals so "invoices" matches "invoice"."""
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def tokenize(text: str) -> list[str]:
    return [_stem(w) for w in _WORD.findall(text.lower()) if w not in _STOPWORDS]


def _slug(text: str) -> str:
    return "-".join(_WORD.findall(text.lower()))


@dataclass(frozen=True)
class Section:
    id: str
    area: str
    title: str
    heading: str
    text: str
    human_only: bool

    @property
    def is_policy(self) -> bool:
        return self.area == POLICY_AREA


def parse_doc(path: Path, root: Path) -> list[Section]:
    """Split one Markdown doc into its `##` sections."""
    rel = path.relative_to(root)
    area = rel.parts[0] if len(rel.parts) > 1 else "general"
    doc_id = rel.with_suffix("").as_posix()
    title = path.stem.replace("-", " ").capitalize()
    sections: list[Section] = []
    heading: str | None = None
    body: list[str] = []

    def flush() -> None:
        if heading is None:
            return
        lines = [line for line in body if line.strip()]
        human_only = bool(lines) and lines[0].strip().lower().startswith(HUMAN_MARKER)
        if human_only:
            lines = lines[1:]
        text = " ".join(line.strip() for line in lines)
        sections.append(
            Section(
                id=f"{doc_id}#{_slug(heading)}",
                area=area,
                title=title,
                heading=heading,
                text=text,
                human_only=human_only,
            )
        )

    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
        elif line.startswith("## "):
            flush()
            heading, body = line[3:].strip(), []
        else:
            body.append(line)
    flush()
    return sections


@dataclass
class KnowledgeBase:
    sections: list[Section]
    k1: float = 1.2
    b: float = 0.75
    _tokens: list[list[str]] = field(init=False, repr=False)
    _idf: dict[str, float] = field(init=False, repr=False)
    _avg_len: float = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._tokens = [
            tokenize(f"{s.title} {s.heading} {s.heading} {s.text}") for s in self.sections
        ]
        n = len(self._tokens)
        df: Counter[str] = Counter()
        for tokens in self._tokens:
            df.update(set(tokens))
        self._idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}
        self._avg_len = (sum(len(t) for t in self._tokens) / n) if n else 0.0

    @classmethod
    def load(cls, root: str | Path) -> "KnowledgeBase":
        root = Path(root)
        files = sorted(p for p in root.rglob("*.md") if p.name.lower() != "readme.md")
        return cls([section for path in files for section in parse_doc(path, root)])

    def get(self, section_id: str) -> Section | None:
        return next((s for s in self.sections if s.id == section_id), None)

    def search(self, query: str, k: int = 4) -> list[Source]:
        """The k best sections for the query, best first. Sections sharing no words are dropped."""
        terms = set(tokenize(query))
        scored: list[tuple[float, Section]] = []
        for section, tokens in zip(self.sections, self._tokens, strict=True):
            counts = Counter(tokens)
            score = 0.0
            for term in terms & counts.keys():
                tf = counts[term]
                norm = tf + self.k1 * (1 - self.b + self.b * len(tokens) / self._avg_len)
                score += self._idf[term] * tf * (self.k1 + 1) / norm
            if score > 0:
                scored.append((score, section))
        scored.sort(key=lambda pair: (-pair[0], pair[1].id))
        return [
            Source(
                id=s.id,
                area=s.area,
                title=s.title,
                heading=s.heading,
                text=s.text,
                human_only=s.human_only,
                policy=s.is_policy,
                score=round(score, 3),
            )
            for score, s in scored[:k]
        ]


@lru_cache
def get_kb() -> KnowledgeBase:
    """The docs named in triage.yaml, or at DOCS_PATH when that is set."""
    return KnowledgeBase.load(get_settings().docs_path or get_org_config().docs_dir)
