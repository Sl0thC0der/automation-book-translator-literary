# Translation Profiles

## Overview

Profiles are JSON files that control how the translator handles a specific genre or book. They live in `examples/profiles/`.

## Included Profiles

| Profile | Use Case | Protected Nouns | Seed Glossary |
|---------|----------|-----------------|---------------|
| `default.json` | General literary fiction | 0 | 0 |
| `lovecraft.json` | Cosmic horror, Cthulhu Mythos | 62 | 10 |
| `fantasy.json` | Epic/high fantasy | 0 | 0 |
| `scifi.json` | Science fiction | 0 | 5 |
| `nonfiction.json` | Technical, popular science | 0 | 0 |
| `thriller.json` | Crime, spy novels | 0 | 0 |

## Profile Fields

```json
{
  "name": "Display name for logs and stats",
  "description": "What this profile is for (documentation only)",
  "source_language": "English",

  "style_instructions": "Instructions for the translator.\nWrite in the TARGET language for best results.\nEach line is a separate instruction.",

  "protected_nouns": ["Names", "that", "must", "never", "be", "translated"],

  "glossary_seed": {
    "source_term": "target_translation"
  },

  "temperature": {
    "translate": 0.3,
    "review": 0.4,
    "refine": 0.2
  },

  "min_review_chars": 300,
  "context_update_interval": 15,
  "glossary_update_interval": 20
}
```

### Field Details

**style_instructions** — The most impactful field. Write in the target language (German instructions → better German output). These are injected into both the translator and reviewer system prompts.

**protected_nouns** — Names/terms that must appear unchanged in the translation. Critical for fantasy/sci-fi with invented terminology. Limit: 60 displayed in prompts.

**glossary_seed** — Pre-seeded translations. Model will auto-discover more during translation. Good for establishing early consistency.

**temperature** — Lower = more literal/consistent, Higher = more creative. The defaults (0.3/0.4/0.2) work well for most literary fiction.

**min_review_chars** — Paragraphs shorter than this skip the review pass. Lower = more reviews = better quality but higher cost. Set to 500+ for non-fiction.

**context_update_interval** — How often to update the rolling narrative summary. Lower = better narrative consistency but more API calls.

**glossary_update_interval** — How often to extract new glossary terms. Lower = better term consistency but more API calls.

## Creating Your Own Profile

```bash
cp examples/profiles/_template.json examples/profiles/my_book.json
# Edit my_book.json

python make_book.py --book_name book.epub -m 3pass-sonnet \
  --single_translate --language de --use_context \
  --translation-profile examples/profiles/my_book.json
```

## Tips

- **Style instructions in target language** — German instructions produce measurably better German output
- **Start with few protected nouns** — add more if you see them being translated
- **Test with 5 paragraphs** before running the full book
- **Glossary seeds are optional** — the auto-extractor usually finds key terms within a few chapters
