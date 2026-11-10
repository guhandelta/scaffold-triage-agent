# Support docs

These are starter docs that most software companies have. The agent reads them to decide how to
handle a ticket and cites the sections it used.

Replace or extend them with your own organization's docs:

- One folder per product area (`account`, `billing`, ...). The folder name becomes the area.
- One Markdown file per topic. The first `# Heading` is the doc title.
- Each `## Section` is retrieved and cited on its own, so keep one answer per section.
- Start a section with `> Handled by a person.` when the agent must never answer it itself.
  The agent escalates those tickets and cites the section as the reason.
- Docs under `policies/` describe how the agent should behave. They guide models but are never
  sent to customers as a reply.

Point the agent at another folder with `docs.path` in `triage.yaml` (or `DOCS_PATH` in `backend/.env`).
