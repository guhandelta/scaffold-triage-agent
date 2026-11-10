# The triage API. Config and docs are read from /org when it is mounted (see docker-compose.yml),
# or from the sample baked into the image.
FROM python:3.13-slim

RUN pip install --no-cache-dir uv==0.11.32

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PATH=/app/.venv/bin:$PATH

# Dependencies first, so code changes do not reinstall them.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app
COPY data/docs ./data/docs
COPY triage.yaml ./

RUN useradd --system --uid 10001 triage \
    && mkdir -p /var/lib/triage \
    && chown triage /var/lib/triage
USER triage

ENV DATABASE_PATH=/var/lib/triage/tickets.db
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
