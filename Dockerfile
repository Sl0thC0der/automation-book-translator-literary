# --- Stage 1: Install dependencies -----------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /install
COPY requirements.txt .
RUN pip install --prefix=/install/deps --no-cache-dir -r requirements.txt \
    && pip install --prefix=/install/deps --no-cache-dir pymupdf

# --- Stage 2: Translator runtime (lightweight) ----------------------------------
FROM python:3.12-slim AS translator

RUN groupadd -r translator && useradd -r -g translator -d /app translator

COPY --from=builder /install/deps /usr/local

WORKDIR /app
COPY book_maker/ book_maker/
COPY make_book.py .
COPY examples/profiles/ /app/profiles/

RUN mkdir -p /books /output && chown -R translator:translator /app /books /output

USER translator

ENTRYPOINT ["python3", "make_book.py"]

# --- Stage 3: Orchestrator (extends translator) ----------------------------------
FROM translator AS orchestrator

USER root

COPY orchestrator/ orchestrator/
COPY run_orchestrator.py .
COPY test_orchestrator_e2e.py .

# Verify bundled CLI binary was installed with the linux wheel
RUN python3 -c "\
from pathlib import Path; \
cli = next(Path('/usr/local/lib').rglob('claude_agent_sdk/_bundled/claude'), None); \
assert cli and cli.exists(), 'Bundled CLI not found'; \
print(f'OK: {cli} ({cli.stat().st_size // 1024 // 1024} MB)')"

RUN mkdir -p /reports \
    && chown -R translator:translator /app /reports

USER translator

ENTRYPOINT ["python3", "run_orchestrator.py"]
