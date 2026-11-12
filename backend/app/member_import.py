"""Read a list of team members from an uploaded file.

- .csv: a header row. Columns are matched by name: name, email, employee id, role. Any other
  column is a team field, matched by its key (for example, start_date).
- .txt, .md, .markdown, .docx: one member per line, with the columns in this order, separated by
  commas: name, email, employee id, role. Blank lines and lines starting with # are skipped.

PDF files are not supported yet. Legacy .doc files are refused, as they are for tickets.
"""

import csv
import io
import re
from pathlib import PurePath

from app.ingest import MAX_BYTES, UploadError, _docx_text

SUPPORTED = (".csv", ".md", ".markdown", ".txt", ".docx")
MAX_ROWS = 500
_COLUMN_NAMES = {"name", "email", "employee_id", "role"}
_TEXT_COLUMNS = ["name", "email", "employee_id", "role"]


def _clean_header(header: str) -> str:
    return re.sub(r"[\s-]+", "_", header.strip().lower())


def _from_csv(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text))
    headers = [_clean_header(h or "") for h in reader.fieldnames or []]
    if "name" not in headers:
        raise UploadError("the CSV needs a name column")
    rows = []
    for number, raw in enumerate(reader, start=2):
        row = {_clean_header(k or ""): (v or "").strip() for k, v in raw.items()}
        rows.append(
            {
                "line": number,
                "name": row.get("name", ""),
                "email": row.get("email", ""),
                "employee_id": row.get("employee_id", ""),
                "role": row.get("role", ""),
                "details": {k: v for k, v in row.items() if k not in _COLUMN_NAMES and k},
            }
        )
    return rows


def _from_text(text: str) -> list[dict]:
    rows = []
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = [p.strip() for p in stripped.split(",")]
        if len(parts) > len(_TEXT_COLUMNS):
            parts_error = f"too many columns; expected {', '.join(_TEXT_COLUMNS)}"
        else:
            parts_error = None
        parts += [""] * (len(_TEXT_COLUMNS) - len(parts))
        row = dict(zip(_TEXT_COLUMNS, parts[: len(_TEXT_COLUMNS)], strict=True))
        rows.append(
            {
                "line": number,
                "name": row["name"],
                "email": row["email"],
                "employee_id": row["employee_id"],
                "role": row["role"],
                "details": {},
                "problem": parts_error,
            }
        )
    return rows


def parse_members(filename: str, data: bytes) -> list[dict]:
    suffix = PurePath(filename or "").suffix.lower()
    if suffix == ".pdf":
        raise UploadError(
            "PDF files are not supported yet; save the list as .docx, .md, .txt or .csv"
        )
    if suffix == ".doc":
        raise UploadError("legacy .doc files are not supported; save the file as .docx")
    if suffix not in SUPPORTED:
        raise UploadError(f"unsupported file type; use one of {', '.join(SUPPORTED)}")
    if len(data) > MAX_BYTES:
        raise UploadError("the file is larger than 2 MB")
    text = _docx_text(data) if suffix == ".docx" else data.decode("utf-8-sig", errors="replace")
    rows = _from_csv(text) if suffix == ".csv" else _from_text(text)
    if len(rows) > MAX_ROWS:
        raise UploadError(f"a file can add at most {MAX_ROWS} members")
    return rows
