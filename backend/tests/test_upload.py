import io

import pytest
from docx import Document
from fastapi.testclient import TestClient

from app.ingest import MAX_BYTES, MAX_TICKETS, UploadError, parse_upload
from app.main import app

client = TestClient(app)


def _docx(*paragraphs: str) -> bytes:
    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_csv_matches_columns_by_name():
    data = (
        "﻿Title,Description,Email\n"
        "Export,How do I export?,a@x.com\n"
        ",,\n"
        "Only a subject,,\n"
        ",Only a body,\n"
    ).encode()
    tickets = parse_upload("t.csv", data)
    assert [(t.subject, t.body, t.customer_email) for t in tickets] == [
        ("Export", "How do I export?", "a@x.com"),
        ("Only a subject", "Only a subject", None),
        ("Only a body", "Only a body", None),
    ]


def test_csv_without_known_columns_is_refused():
    with pytest.raises(UploadError, match="subject or body column"):
        parse_upload("t.csv", b"foo,bar\n1,2\n")


def test_csv_with_no_header_is_refused():
    with pytest.raises(UploadError, match="subject or body column"):
        parse_upload("t.csv", b"")


def test_markdown_blocks_are_split_by_dashes():
    text = "# Export\nHow do I export?\nThanks\n---\n\n----\nJust one line\n"
    tickets = parse_upload("t.MD", text.encode())
    assert [(t.subject, t.body) for t in tickets] == [
        ("Export", "How do I export?\nThanks"),
        ("Just one line", "Just one line"),
    ]


def test_text_and_markdown_suffixes():
    assert parse_upload("a.txt", b"Hi\nbody")[0].subject == "Hi"
    assert parse_upload("a.markdown", b"Hi\nbody")[0].body == "body"


def test_heading_only_block_is_refused():
    with pytest.raises(UploadError, match="empty"):
        parse_upload("t.md", b"#\n")


def test_docx_is_read_by_paragraph():
    data = _docx("Login broken", "I cannot sign in.", "---", "Invoice", "Where is it?")
    tickets = parse_upload("t.docx", data)
    assert [(t.subject, t.body) for t in tickets] == [
        ("Login broken", "I cannot sign in."),
        ("Invoice", "Where is it?"),
    ]


def test_bad_docx_is_refused():
    with pytest.raises(UploadError, match="could not read"):
        parse_upload("t.docx", b"not a zip")


@pytest.mark.parametrize(
    ("name", "data", "message"),
    [
        ("t.doc", b"x", "save the file as .docx"),
        ("t.pdf", b"x", "unsupported file type"),
        ("", b"x", "unsupported file type"),
        ("t.txt", b"x" * (MAX_BYTES + 1), "larger than 2 MB"),
        ("t.txt", b"\xff\xfe\x00", "not UTF-8"),
        ("t.txt", b"  \n---\n", "no tickets"),
        ("t.txt", "\n---\n".join(["t"] * (MAX_TICKETS + 1)).encode(), "the limit is 50"),
    ],
)
def test_bad_files_are_refused(name, data, message):
    with pytest.raises(UploadError, match=message):
        parse_upload(name, data)


def test_upload_triages_every_ticket():
    text = "Export data\nHow do I export my project data? It is large.\n---\nRefund\nMoney back"
    r = client.post("/api/tickets/upload", files={"file": ("batch.md", text, "text/markdown")})
    assert r.status_code == 200
    body = r.json()
    assert body["filename"] == "batch.md"
    assert [rec["decision"]["action"] for rec in body["records"]] == ["reply", "escalate"]
    assert len(client.get("/api/tickets").json()) == 2


def test_upload_reports_parse_errors():
    r = client.post("/api/tickets/upload", files={"file": ("old.doc", b"x")})
    assert r.status_code == 422
    assert "docx" in r.json()["detail"]
