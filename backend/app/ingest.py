"""Turn an uploaded file into tickets.

Supported:
- .csv: one ticket per row. Columns are matched by name: subject/title, body/description/
  message/issue, and email/customer_email.
- .md, .txt, .docx: tickets separated by a line of three or more dashes (---). In each block
  the first line is the subject (a leading # is dropped) and the rest is the body. A block with
  one line uses it for both.

Legacy Word .doc files are binary and cannot be read reliably, so they are refused with a hint
to save them as .docx.
"""

import csv
import io
import re
from pathlib import PurePath

from pydantic import ValidationError

from app.schemas import TicketIn

MAX_BYTES = 2 * 1024 * 1024
MAX_TICKETS = 50
SUPPORTED = (".csv", ".md", ".markdown", ".txt", ".docx")

_SUBJECT_COLUMNS = ("subject", "title", "summary")
_BODY_COLUMNS = ("body", "description", "message", "issue", "text", "content")
_EMAIL_COLUMNS = ("customer_email", "email", "from")
_SEPARATOR = re.compile(r"^\s*-{3,}\s*$", re.MULTILINE)


class UploadError(ValueError):
    pass


def _pick(row: dict[str, str], names: tuple[str, ...]) -> str:
    for name in names:
        value = row.get(name)
        if value and value.strip():
            return value.strip()
    return ""


def _from_csv(text: str) -> list[TicketIn]:
    reader = csv.DictReader(io.StringIO(text))
    headers = [h.strip().lower() for h in reader.fieldnames or []]
    if not any(h in _BODY_COLUMNS or h in _SUBJECT_COLUMNS for h in headers):
        raise UploadError(
            "the CSV needs a subject or body column (for example: subject, body, email)"
        )
    tickets = []
    for raw in reader:
        row = {(k or "").strip().lower(): (v or "") for k, v in raw.items()}
        subject = _pick(row, _SUBJECT_COLUMNS)
        body = _pick(row, _BODY_COLUMNS)
        if not subject and not body:
            continue
        email = _pick(row, _EMAIL_COLUMNS) or None
        tickets.append(_ticket(subject or body, body or subject, email))
    return tickets


def _from_text(text: str) -> list[TicketIn]:
    tickets = []
    for block in _SEPARATOR.split(text):
        lines = [line.rstrip() for line in block.strip().splitlines()]
        if not lines:
            continue
        subject = lines[0].lstrip("#").strip()
        body = "\n".join(lines[1:]).strip()
        tickets.append(_ticket(subject or body, body or subject, None))
    return tickets


def _docx_text(data: bytes) -> str:
    from docx import Document

    try:
        document = Document(io.BytesIO(data))
    except Exception:
        raise UploadError("could not read the .docx file") from None
    return "\n".join(p.text for p in document.paragraphs)


def _ticket(subject: str, body: str, email: str | None) -> TicketIn:
    try:
        return TicketIn(subject=subject[:300], body=body[:20_000], customer_email=email)
    except ValidationError:
        raise UploadError("a ticket in the file is empty") from None


def parse_upload(filename: str, data: bytes) -> list[TicketIn]:
    suffix = PurePath(filename or "").suffix.lower()
    if suffix == ".doc":
        raise UploadError("legacy .doc files are not supported; save the file as .docx")
    if suffix not in SUPPORTED:
        raise UploadError(f"unsupported file type; use one of {', '.join(SUPPORTED)}")
    if len(data) > MAX_BYTES:
        raise UploadError("the file is larger than 2 MB")

    if suffix == ".docx":
        tickets = _from_text(_docx_text(data))
    else:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise UploadError("the file is not UTF-8 text") from None
        tickets = _from_csv(text) if suffix == ".csv" else _from_text(text)

    if not tickets:
        raise UploadError("no tickets found in the file")
    if len(tickets) > MAX_TICKETS:
        raise UploadError(f"the file has {len(tickets)} tickets; the limit is {MAX_TICKETS}")
    return tickets
