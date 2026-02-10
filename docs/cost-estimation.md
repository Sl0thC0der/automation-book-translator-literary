# Cost Estimation

## Pricing (as of 2025)

| Model | Input | Output | Cache Read | Cache Write |
|-------|-------|--------|------------|-------------|
| Claude Opus 4 | $15/MTok | $75/MTok | $1.50/MTok | $18.75/MTok |
| Claude Sonnet 4 | $3/MTok | $15/MTok | $0.30/MTok | $3.75/MTok |

## 100,000-Word Book (~5,000 paragraphs)

### With block_size + prompt caching (recommended)

| Component | API Calls | Sonnet | Opus |
|-----------|-----------|--------|------|
| Pass 1 (translate) | ~330 | $4 | $20 |
| Pass 2 (review) | ~330 | $4 | $22 |
| Pass 3 (refine, ~40%) | ~130 | $2 | $10 |
| Context updates | ~22 | $0.5 | $2 |
| Glossary extraction | ~17 | $0.3 | $1 |
| **Total** | **~830** | **~$10-15** | **~$50-70** |

### Without block_size (per-paragraph)

| Component | API Calls | Sonnet | Opus |
|-----------|-----------|--------|------|
| Pass 1 | ~5,000 | $12 | $60 |
| Pass 2 (long only) | ~2,000 | $8 | $40 |
| Pass 3 (~40%) | ~800 | $4 | $20 |
| Context/glossary | ~40 | $1 | $3 |
| **Total** | **~8,000** | **~$25-35** | **~$120-170** |

### Skip-review mode (--skip-review)

Pass 1 only, no review/refine. ~40% cheaper than full 3-pass.

| Mode | Sonnet | Opus |
|------|--------|------|
| block_size + skip-review | ~$6-8 | ~$30-40 |
| per-paragraph + skip-review | ~$15-20 | ~$70-90 |

## Cost Optimization Tips

1. **Always use `--single_translate`** — auto-enables block mode, 3-10× cheaper
2. **Test first**: `--test --test_num 5` before committing to a full book
3. **Sonnet for drafts, Opus for final** — iterate on Sonnet, then do one Opus run
4. **Profile tuning**: increase `min_review_chars` to skip reviews on more paragraphs
5. **Skip review for technical/non-fiction** — `--skip-review` works well for non-literary content
