# Architecture

## 3-Pass Translation Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                    epub_loader (upstream)                     │
│  Extracts paragraphs → calls translate() → rebuilds epub     │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                  Claude3Pass.translate()                      │
│                                                              │
│  ┌─────────────┐   ┌──────────────┐   ┌──────────────────┐ │
│  │ Short (<300c)│   │ Long (≥300c) │   │ Batch (\n delim) │ │
│  │ → Pass 1    │   │ → 3-pass     │   │ → 3-pass batch   │ │
│  └──────┬──────┘   └──────┬───────┘   └────────┬─────────┘ │
│         │                  │                     │           │
│         ▼                  ▼                     ▼           │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Pass 1: TRANSLATE                                    │    │
│  │ System prompt + glossary + context → raw translation │    │
│  └──────────────────────────┬──────────────────────────┘    │
│                              │                               │
│                              ▼                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Pass 2: REVIEW                                       │    │
│  │ Original + translation → error list or QUALITY_OK    │    │
│  └──────────────────────────┬──────────────────────────┘    │
│                              │                               │
│                    ┌─────────┴─────────┐                    │
│                    │                   │                     │
│              QUALITY_OK          Issues found                │
│                    │                   │                     │
│                    ▼                   ▼                     │
│              Return P1       ┌──────────────────┐           │
│                              │ Pass 3: REFINE   │           │
│                              │ Apply all fixes   │           │
│                              └────────┬─────────┘           │
│                                       │                     │
│                                       ▼                     │
│                                 Return refined              │
└─────────────────────────────────────────────────────────────┘
```

## Shared State

The translator maintains two pieces of state across the entire book:

### Rolling Context Summary
Updated every N chunks (configurable via `context_update_interval`). Captures characters, locations, mood. Fed into every Pass 1 system prompt so the model knows where the story is.

### Auto-Expanding Glossary
Seeded from profile, expanded every N chunks via glossary extraction API call. Ensures terms like "warp drive" are translated consistently as "Warp-Antrieb" throughout.

## Prompt Caching

The system prompt (~600-800 tokens) is identical for every Pass 1 call (minus the dynamic glossary/context). Claude's prompt caching gives:
- First call: +25% for cache write
- All subsequent: **90% discount** on cached input tokens

Over 1,300+ calls for a book, this saves $30-50 on Opus.

## Batch Mode

When `--single_translate` is used (recommended), epub_loader combines multiple paragraphs with `\n` delimiters. The translator:

1. Detects multi-paragraph input (`\n` in text)
2. Replaces `\n` with `|||PARA|||` delimiter (model-safe)
3. Processes entire batch through 3-pass
4. Splits result back on `|||PARA|||`
5. Strips internal newlines to prevent epub_loader corruption
6. Handles paragraph count mismatch (merge extras / pad missing)

This amortizes system prompt cost across many paragraphs — cutting API calls from ~14,500 to ~1,300 for a 100k-word book.
