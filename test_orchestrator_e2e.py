#!/usr/bin/env python3
"""End-to-end test of the orchestrator pipeline.

Runs all orchestrator tool functions in sequence (same workflow the Agent SDK
would drive), bypassing the SDK subprocess transport that has issues on Windows.
"""

import json
import os
import sys
import time

# Ensure API key is set
if not os.environ.get("ANTHROPIC_API_KEY"):
    print("ERROR: Set ANTHROPIC_API_KEY first")
    sys.exit(1)


def step(name):
    print(f"\n{'=' * 60}")
    print(f"  STEP: {name}")
    print(f"{'=' * 60}\n")


def pretty(json_str):
    """Pretty-print a JSON string."""
    try:
        data = json.loads(json_str)
        return json.dumps(data, indent=2, ensure_ascii=False)
    except (json.JSONDecodeError, TypeError):
        return str(json_str)


def main():
    book_path = "test_books/animal_farm.epub"
    test_num = 10
    language = "de"
    model = "3pass-sonnet"
    profiles_dir = "examples/profiles"
    report_dir = "."

    print(f"Full Orchestrator E2E Test")
    print(f"  Book: {book_path}")
    print(f"  Language: {language}")
    print(f"  Model: {model}")
    print(f"  Paragraphs: {test_num}")
    print(f"  Profiles dir: {profiles_dir}")

    t0 = time.time()

    # ── Step 1: Analyze book ──────────────────────────────────────────
    step("1/6 — Analyze Book")
    from orchestrator.tools.analyze import analyze_book

    analysis_json = analyze_book(book_path=book_path, sample_count=3)
    analysis = json.loads(analysis_json)
    print(f"  Title: {analysis.get('title', 'Unknown')}")
    print(f"  Chapters: {analysis.get('chapters', '?')}")
    print(f"  Total paragraphs: {analysis.get('total_paragraphs', '?')}")
    print(f"  Source language: {analysis.get('source_language', '?')}")
    print(f"  Word count: {analysis.get('word_count', '?')}")
    if "cost_estimates" in analysis:
        est = analysis["cost_estimates"]
        print(f"  Cost estimates: Sonnet ~${est.get('sonnet_with_cache', '?')}, "
              f"Opus ~${est.get('opus_with_cache', '?')}")

    source_lang = analysis.get("source_language", "English")

    # ── Step 2: List profiles ─────────────────────────────────────────
    step("2/6 — List Profiles & Select")
    from orchestrator.tools.profiles import list_profiles

    profiles_json = list_profiles(profiles_dir=profiles_dir)
    profiles = json.loads(profiles_json)

    print(f"  Found {len(profiles.get('profiles', []))} profiles:")
    selected_profile = None
    for p in profiles.get("profiles", []):
        name = p.get("name", "?")
        desc = p.get("description", "")[:60]
        print(f"    - {name}: {desc}")
        # Pick the "classic" or "literary" profile if available
        if "classic" in name.lower() or "literary" in name.lower():
            selected_profile = p.get("path", "")

    # Fallback: pick first non-template profile
    if not selected_profile:
        for p in profiles.get("profiles", []):
            path = p.get("path", "")
            if "_template" not in path and path:
                selected_profile = path
                break

    if selected_profile:
        print(f"\n  Selected profile: {selected_profile}")
    else:
        print("\n  No profile found, using defaults")
        selected_profile = ""

    # ── Step 3: Translate (10 paragraphs) ─────────────────────────────
    step(f"3/6 — Translate ({test_num} paragraphs)")
    from orchestrator.tools.translate import run_translation

    translate_json = run_translation(
        book_path=book_path,
        language=language,
        model=model,
        profile_path=selected_profile,
        use_context=True,
        skip_review=False,
        test_mode=True,
        test_num=test_num,
        block_size=1500,
        resume=False,
        source_lang="en",
    )
    translate_result = json.loads(translate_json)

    if translate_result.get("error"):
        print(f"  ERROR: {translate_result['error']}")
        sys.exit(1)

    output_path = translate_result.get("output_path", "")
    stats = translate_result.get("stats", {})
    print(f"  Status: {translate_result.get('status', '?')}")
    print(f"  Output: {output_path}")
    print(f"  Chunks: {translate_result.get('chunks_processed', '?')}")
    print(f"  API calls: {stats.get('total_requests', '?')}")
    print(f"  Tokens: {stats.get('total_input_tokens', 0):,} in / {stats.get('total_output_tokens', 0):,} out")
    print(f"  Cost: ${stats.get('cost_estimate', 0):.2f}")
    print(f"  P1-only: {stats.get('pass1_only_count', 0)} | "
          f"3-pass: {stats.get('full_3pass_count', 0)} | "
          f"OK: {stats.get('reviews_ok', 0)} | "
          f"Fixed: {stats.get('reviews_fixed', 0)}")

    # ── Step 4: Extract paragraph pairs for quality check ─────────────
    step("4/6 — Extract Paragraph Pairs")
    from orchestrator.tools.quality import extract_paragraphs, quality_spot_check

    if output_path and os.path.exists(output_path):
        pairs_json = extract_paragraphs(
            original_path=book_path,
            translated_path=output_path,
            sample_count=3,
            strategy="first",
        )
        pairs = json.loads(pairs_json)
        pair_list = pairs.get("pairs", [])
        print(f"  Extracted {len(pair_list)} paragraph pairs")
        for i, pair in enumerate(pair_list[:3]):
            orig = pair.get("original", "")[:80]
            trans = pair.get("translated", "")[:80]
            print(f"\n  Pair {i+1}:")
            print(f"    EN: {orig}...")
            print(f"    DE: {trans}...")
    else:
        print(f"  WARNING: Output file not found at {output_path}")
        pair_list = []

    # ── Step 5: Quality spot-check ────────────────────────────────────
    step("5/6 — Quality Spot-Check")
    quality_results = []

    if pair_list:
        # Check up to 2 pairs (to save API calls)
        check_count = min(2, len(pair_list))
        for i in range(check_count):
            pair = pair_list[i]
            print(f"\n  Checking pair {i+1}/{check_count}...")
            qc_json = quality_spot_check(
                original_text=pair.get("original", ""),
                translated_text=pair.get("translated", ""),
                source_language=source_lang,
                target_language="German",
            )
            qc = json.loads(qc_json)
            quality_results.append(qc)

            overall = qc.get("overall_score", "?")
            print(f"    Overall score: {overall}/5")
            for dim, score in qc.get("scores", {}).items():
                print(f"      {dim}: {score}/5")
            if qc.get("issues"):
                for issue in qc["issues"][:3]:
                    print(f"    Issue: {issue}")

        if quality_results:
            avg_score = sum(r.get("overall_score", 0) for r in quality_results) / len(quality_results)
            print(f"\n  Average quality score: {avg_score:.1f}/5")
    else:
        print("  Skipped — no paragraph pairs available")

    # ── Step 6: Generate report ───────────────────────────────────────
    step("6/6 — Generate Report")
    from orchestrator.tools.report import generate_report

    report_path = os.path.join(report_dir, "translation_report.md")
    report_json = generate_report(
        translation_stats=json.dumps(stats),
        quality_results=json.dumps(quality_results),
        book_metadata=analysis_json,
        profile_name=os.path.basename(selected_profile) if selected_profile else "Default",
        model_used=model,
        output_path=report_path,
    )
    report_result = json.loads(report_json)
    print(f"  Report saved to: {report_result.get('path', report_path)}")

    # ── Summary ───────────────────────────────────────────────────────
    elapsed = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"  ORCHESTRATION COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Total time: {elapsed:.0f}s")
    print(f"  Paragraphs translated: {test_num}")
    print(f"  API cost (translation): ${stats.get('cost_estimate', 0):.2f}")
    print(f"  Output: {output_path}")
    print(f"  Report: {report_path}")
    if quality_results:
        avg = sum(r.get("overall_score", 0) for r in quality_results) / len(quality_results)
        print(f"  Quality score: {avg:.1f}/5")
    print()


if __name__ == "__main__":
    main()
