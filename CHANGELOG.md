# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-02-10

### Added
- 3-pass literary translation pipeline (translate → review → refine)
- Loadable genre profiles (lovecraft, fantasy, scifi, nonfiction, thriller)
- Prompt caching for ~60% cost reduction on repeated system prompts
- Smart dispatch: short paragraphs → pass 1 only, long → full 3-pass
- Batch mode: multiple paragraphs per API call via --single_translate
- Rolling narrative context summary for consistency across chapters
- Auto-expanding glossary with per-profile seed terms
- Protected proper nouns system (configurable per profile)
- Source language detection and explicit prompting
- Cost estimation with cache-aware pricing
- Final stats report with token counts, cache savings, cost breakdown
- Wrapper script (scripts/translate.sh) for common operations
- Multi-stage Dockerfile with non-root user
- Docker Compose with output volume, resource limits, init
- Full documentation (architecture, cost estimation, profiles, troubleshooting)

### Based on
- [bilingual_book_maker](https://github.com/yihong0618/bilingual_book_maker) by yihong0618
- All original features remain fully functional
