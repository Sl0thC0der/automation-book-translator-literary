# automation-book-translator-literary

> 3-pass literary translation pipeline with genre profiles, prompt caching, and containerized deployment.

## Overview

A fork of [bilingual_book_maker](https://github.com/yihong0618/bilingual_book_maker) that adds a **3-pass literary translation pipeline** using the Claude API. Translates books (epub, pdf, txt) with published-quality results by running each passage through translate → review → refine passes, with rolling context and auto-expanding glossary for book-length consistency.

Works for **any language pair**. Loadable **genre profiles** control style, protected proper nouns, glossary seeds, and tuning parameters.

All original bilingual_book_maker features remain fully functional.

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Examples](#examples)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Project Structure](#project-structure)
- [Contributing](#contributing)
- [License](#license)

## Features

- 3-pass pipeline: translate → review → refine (skip-review mode available)
- Smart dispatch: short paragraphs get pass 1 only, long paragraphs get full 3-pass
- Batch mode: multiple paragraphs per API call, cutting costs by 3-10×
- Prompt caching: 90% discount on repeated system prompts (~$30-50 saved on Opus)
- Rolling narrative context: tracks characters, locations, mood across chapters
- Auto-expanding glossary: consistent terminology throughout the book
- Protected proper nouns: names/terms that must never be translated (per profile)
- Genre profiles: lovecraft, fantasy, scifi, nonfiction, thriller, or custom
- Explicit source/target language in all prompts
- Final stats: token counts, cache savings, cost breakdown
- Multi-stage Docker build with non-root user

## Prerequisites

### Required
- Python 3.10+ (tested with 3.12)
- Anthropic API key with access to Claude Sonnet 4 or Opus 4

### Optional
- Docker & Docker Compose (for containerized deployment)

### Platform Notes
- **Linux/macOS**: Full support including shell scripts (`scripts/*.sh`) and `make` targets
- **Windows**: Use `python make_book.py` directly (shell scripts require WSL/Git Bash)

## Installation

### Quick Start
```bash
git clone <repository-url>
cd automation-book-translator-literary

./scripts/setup.sh
```

### Manual Installation
```bash
pip install -r requirements.txt
pip install pymupdf

export ANTHROPIC_API_KEY=sk-ant-XXXXX
```

## Usage

### Basic Usage
```bash
# EN→DE with Sonnet (recommended starting point)
python make_book.py --book_name book.epub -m 3pass-sonnet \
  --single_translate --language de --use_context

# Always test first!
python make_book.py --book_name book.epub -m 3pass-sonnet \
  --single_translate --language de --use_context \
  --test --test_num 5
```

### With Wrapper Script
```bash
./scripts/translate.sh book.epub                              # EN→DE Sonnet
./scripts/translate.sh book.epub -p lovecraft -m opus         # Lovecraft, Opus
./scripts/translate.sh book.epub -l fr -p scifi               # EN→FR sci-fi
./scripts/translate.sh book.epub -t 5                         # Test 5 paragraphs
```

### With Make
```bash
make translate BOOK=book.epub PROFILE=lovecraft MODEL=opus
make translate-test BOOK=book.epub                            # Test 5 paras
make profiles                                                 # List profiles
```

### Advanced Usage
```bash
# Opus for highest quality, with genre profile
python make_book.py --book_name lovecraft.epub -m 3pass-opus \
  --single_translate --language de --use_context \
  --translation-profile examples/profiles/lovecraft.json

# Skip review (cheaper, ~40% savings)
python make_book.py --book_name book.epub -m 3pass-sonnet \
  --single_translate --language de --use_context \
  --skip-review

# Resume after interruption
python make_book.py --book_name book.epub -m 3pass-sonnet \
  --single_translate --language de --use_context \
  --resume
```

## Configuration

### Environment Variables
```bash
export ANTHROPIC_API_KEY=sk-ant-XXXXX    # Required for 3pass models
# or
export BBM_CLAUDE_API_KEY=sk-ant-XXXXX   # Alternative (checked first)
```

For 3pass models, the key is resolved in order: `--claude_key` flag → `BBM_CLAUDE_API_KEY` → `ANTHROPIC_API_KEY`.

### Models

| Model | Claude Engine | Quality | Cost (100k words) |
|-------|-------------|---------|-------------------|
| `3pass` | Sonnet (default) | Very good | ~$10-15 |
| `3pass-sonnet` | Sonnet 4 | Very good | ~$10-15 |
| `3pass-opus` | Opus 4 | Best | ~$50-70 |

### Key Flags

| Flag | Description |
|------|------------|
| `-m 3pass` / `3pass-opus` / `3pass-sonnet` | Select model |
| `--language LANG` | Target language (de, fr, es, ja, zh-hans, etc.) |
| `--translation-profile PATH` | Load a genre profile JSON |
| `--single_translate` | Target-only output, enables auto batch mode |
| `--use_context` | Enable rolling context summary |
| `--skip-review` | Skip pass 2+3, pass 1 only (cheaper) |
| `--block_size N` | Override auto batch size (default: 1500) |
| `--test --test_num N` | Translate first N paragraphs only |
| `--resume` | Resume from saved state |

### Genre Profiles

Profiles live in `examples/profiles/`:

| Profile | Use Case |
|---------|----------|
| `default.json` | General literary fiction |
| `lovecraft.json` | Cosmic horror, Cthulhu Mythos (62 protected nouns) |
| `fantasy.json` | Epic/high fantasy |
| `scifi.json` | Science fiction |
| `nonfiction.json` | Technical books, popular science |
| `thriller.json` | Crime fiction, spy novels |
| `_template.json` | Documented template for custom profiles |

See [docs/profiles.md](docs/profiles.md) for full documentation.

## Examples

### Example 1: Basic EN→DE Translation
```bash
./scripts/translate.sh book.epub
```

### Example 2: Lovecraft with Opus (Highest Quality)
```bash
./scripts/translate.sh lovecraft.epub -p lovecraft -m opus
```

### Example 3: Custom Profile
```bash
cp examples/profiles/_template.json examples/profiles/my_book.json
# Edit my_book.json with your style instructions, protected nouns, etc.

./scripts/translate.sh book.epub -p my_book
```

### Example 4: Docker Deployment
```bash
mkdir -p books output
cp book.epub books/
export ANTHROPIC_API_KEY=sk-ant-XXXXX

docker compose run --rm translator \
  --book_name /books/book.epub \
  -m 3pass-sonnet \
  --single_translate --language de --use_context
```

## Testing

### Run Tests
```bash
# Integration test (no API key needed — uses mocks)
./scripts/test-translation.sh

# or via Make
make test

# Upstream tests
make test-upstream
```

### Test a Translation (requires API key)
```bash
# Translate 5 paragraphs as smoke test
make translate-test BOOK=book.epub PROFILE=lovecraft
```

## Troubleshooting

### Common Issues

#### API Key Not Found
**Problem:** `Exception: Please provide Anthropic API key`

**Solution:**
```bash
export ANTHROPIC_API_KEY=sk-ant-XXXXX
```

#### Rate Limiting
**Problem:** Repeated `RateLimitError, retry in Xs`

**Solution:** Built-in exponential backoff handles this. For sustained limits, reduce batch size:
```bash
--block_size 800
```

See [docs/troubleshooting.md](docs/troubleshooting.md) for more.

## Project Structure

```
.
├── README.md                       # This file
├── CHANGELOG.md                    # Version history
├── CONTRIBUTING.md                 # Contribution guidelines
├── LICENSE                         # MIT License
├── Makefile                        # Build/translate/test targets
├── Dockerfile                      # Multi-stage, non-root, Python 3.12
├── docker-compose.yml              # With output volume, resource limits
├── make_book.py                    # Entry point
├── requirements.txt                # Python dependencies
├── pyproject.toml                  # Project metadata
├── .editorconfig                   # Editor configuration
├── .dockerignore                   # Docker build exclusions
├── .gitignore                      # Git exclusions
├── book_maker/                     # Source code (upstream + 3pass translator)
│   ├── translator/
│   │   ├── claude_3pass_translator.py  # ← 3-pass pipeline (new, 633 lines)
│   │   ├── claude_translator.py        # Original Claude translator (unchanged)
│   │   ├── __init__.py                 # +3 model registrations
│   │   └── ...                         # All other translators (unchanged)
│   ├── loader/
│   │   ├── epub_loader.py              # EPUB processing (unchanged)
│   │   └── ...
│   └── cli.py                          # +35 lines for 3pass config
├── docs/
│   ├── architecture.md             # Pipeline architecture & data flow
│   ├── cost-estimation.md          # Detailed cost analysis
│   ├── profiles.md                 # Profile system documentation
│   ├── troubleshooting.md          # Common issues & solutions
│   └── upstream/                   # Original bilingual_book_maker docs
├── examples/
│   └── profiles/                   # Translation profiles
│       ├── _template.json          # Documented template
│       ├── default.json            # General literary
│       ├── lovecraft.json          # Cosmic horror (62 nouns, 10 glossary)
│       ├── fantasy.json            # Epic fantasy
│       ├── scifi.json              # Science fiction
│       ├── nonfiction.json         # Technical / non-fiction
│       └── thriller.json           # Crime / thriller
├── scripts/
│   ├── setup.sh                    # Environment setup & validation
│   ├── translate.sh                # Translation wrapper with shortcuts
│   └── test-translation.sh         # Integration tests (no API key needed)
├── tests/                          # Upstream tests
└── test_books/                     # Sample books for testing
```

## Documentation

- [Architecture](docs/architecture.md) — Pipeline design, batch mode, prompt caching
- [Cost Estimation](docs/cost-estimation.md) — Detailed cost analysis by model and mode
- [Profiles](docs/profiles.md) — Profile system, field reference, creation guide
- [Troubleshooting](docs/troubleshooting.md) — Common issues and solutions
- [Upstream Docs](docs/upstream/) — Original bilingual_book_maker documentation

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.

## Acknowledgments

- [bilingual_book_maker](https://github.com/yihong0618/bilingual_book_maker) by yihong0618 — the upstream project
- [Anthropic Claude API](https://docs.anthropic.com/) — translation engine
- 3-pass pipeline and profiles built with Claude

---

**Status:** Active Development
**Version:** 1.0.0
**Last Updated:** 2026-02-10
