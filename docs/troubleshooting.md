# Troubleshooting

## API Key Not Found

**Problem:** `Exception: Please provide Anthropic API key`

**Solution:**
```bash
export ANTHROPIC_API_KEY=sk-ant-XXXXX
# or
export BBM_CLAUDE_API_KEY=sk-ant-XXXXX
```

## Rate Limiting

**Problem:** Repeated `RateLimitError, retry in Xs` messages

**Solution:** The translator has built-in exponential backoff (3-60s). For sustained rate limiting, reduce batch size:
```bash
--block_size 800  # smaller batches = fewer tokens per call
```

## Paragraph Count Mismatch in Batch Mode

**Problem:** `(merged 12→10 paras)` or `(padded 8→10 paras)` messages

**Cause:** The model sometimes splits or merges paragraphs despite instructions. The translator handles this automatically by merging extras or padding with originals. Occasional mismatches are normal and don't affect quality significantly.

**If frequent:** Lower `--block_size` to reduce paragraphs per batch.

## Glossary JSON Parse Failures

**Problem:** `(glossary JSON parse failed: ...)` messages

**Cause:** Model occasionally returns malformed JSON for glossary extraction. The translator suppresses warnings after 6 failures. This doesn't affect translation quality — it just means fewer auto-discovered glossary terms.

## Docker: Translated Book Not Appearing

**Problem:** Translation completes but no output file

**Solution:** The output is in the same directory as the input book. With Docker:
```bash
# Ensure volumes are correct
docker compose -f docker-compose.yml run --rm translator \
  --book_name /books/input.epub ...
# Output: ./books/input_translated.epub
```

## Context/Glossary Not Working

**Problem:** Translations seem inconsistent across chapters

**Cause:** Likely using `--parallel-workers > 1`. The CLI should auto-disable this, but if you're passing it manually:
```bash
# WRONG: parallel workers corrupt shared state
--parallel-workers 4

# RIGHT: sequential processing
# (don't pass --parallel-workers at all)
```

## Model Not Found / Authentication Error

**Problem:** `NotFoundError` or `AuthenticationError`

**Solution:** Ensure your API key has access to the model:
- `3pass-sonnet` → requires access to `claude-sonnet-4-20250514`
- `3pass-opus` → requires access to `claude-opus-4-20250514`

Check at https://console.anthropic.com
