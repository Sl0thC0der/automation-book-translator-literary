# ─── Stage 1: Install dependencies ───────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /install
COPY requirements.txt .
RUN pip install --prefix=/install/deps --no-cache-dir -r requirements.txt \
    && pip install --prefix=/install/deps --no-cache-dir pymupdf

# ─── Stage 2: Runtime ────────────────────────────────────────────────────────
FROM python:3.12-slim

RUN groupadd -r translator && useradd -r -g translator -d /app translator

COPY --from=builder /install/deps /usr/local

WORKDIR /app
COPY book_maker/ book_maker/
COPY make_book.py .
COPY examples/profiles/ /app/profiles/

RUN mkdir -p /books /output && chown -R translator:translator /app /books /output

USER translator

ENTRYPOINT ["python3", "make_book.py"]
