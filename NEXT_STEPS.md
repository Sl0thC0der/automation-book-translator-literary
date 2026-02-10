# Next Steps

Current state: core translator is production-ready, orchestrator is functional but has rough edges. Docker setup complete for both targets.

---

## Bugs

### quality_spot_check return format mismatch
`orchestrator/tools/quality.py` returns `"average"` key but `test_orchestrator_e2e.py` expects `"overall_score"`. E2E test will silently get `None` for quality scores.

**Fix:** Align on one key name in both files.

---

## Short-Term (polish what exists)

### 1. Wire orchestrator options through CLI dispatch
`cli.py` orchestrator dispatch (~line 441) doesn't forward `--skip-analysis`, `--skip-test`, `--skip-quality-check`, `--test-num`, `--profiles-dir`, `--report-dir`. Users calling `make_book.py --orchestrator` can't customize these — only `run_orchestrator.py` exposes them.

### 2. Aggregated cost tracking
Quality spot-checks make separate Sonnet API calls not counted in translation stats. The orchestrator system prompt says "track costs throughout" but there's no aggregated total (translation + quality evals + orchestration overhead).

### 3. Orchestrator progress feedback
`run_translation` tool registers `on_chunk_complete` but doesn't relay progress to the agent. Users see only final result, not live progress during long translations.

### 4. Orchestrator error recovery
No explicit error handling for tool failures beyond the SDK's `max_turns=30` limit. Transient API errors cause retries without backoff.

---

## Medium-Term (extend capabilities)

### 5. Orchestrator resume/checkpoint
`resume=True` only applies to the translation step. If the full orchestration is interrupted (e.g., during quality review), must restart from scratch. Need checkpoint/resume for the full 6-step workflow.

### 6. Intelligent profile matching
`profile-creator` subagent lists profiles but has no matching algorithm. Could auto-match based on detected genre from `analyze_book` metadata + text samples.

### 7. Genre-aware model recommendation
`book-analyzer` agent doesn't differentiate well between sonnet/opus recommendations. Could use genre detection + book length to recommend: opus for literary fiction, sonnet for everything else.

### 8. Glossary/context visibility
Orchestrator doesn't expose `context_update_interval` or `glossary_update_interval` options. Quality reports don't include glossary state or context evolution.

### 9. Parallel subagent execution
`book-analyzer` and `profile-creator` could run concurrently. Quality checks on multiple paragraph pairs are sequential.

---

## Low Priority

### 10. Windows .bat wrapper
Windows users must use `python run_orchestrator.py` directly. A `run_orchestrator.bat` wrapper would match the bash scripts in `scripts/`.

### 11. Documentation gaps
- README doesn't mention orchestrator is experimental or list known limitations
- `docs/cost-estimation.md` doesn't account for quality check costs
- No guidance for non-German language profiles beyond "create a new profile"
