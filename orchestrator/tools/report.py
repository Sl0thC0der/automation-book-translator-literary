"""Report generation tool — create markdown translation quality/cost reports."""

import json
import os
from datetime import datetime


def generate_report(
    translation_stats: str = "{}",
    quality_results: str = "{}",
    book_metadata: str = "{}",
    profile_name: str = "Default",
    model_used: str = "claude-sonnet-4-20250514",
    output_path: str = "",
) -> str:
    """Generate a markdown translation quality/cost report.

    Args:
        translation_stats: JSON string with TranslationStats data
        quality_results: JSON string with quality spot-check results
        book_metadata: JSON string with book analysis data
        profile_name: Name of the translation profile used
        model_used: Model ID used for translation
        output_path: Where to save the report (default: auto-generate)

    Returns:
        JSON string with report path and summary.
    """
    try:
        stats = json.loads(translation_stats) if translation_stats else {}
        quality = json.loads(quality_results) if quality_results else {}
        metadata = json.loads(book_metadata) if book_metadata else {}
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON input: {e}"})

    # Auto-generate output path
    if not output_path:
        title = metadata.get("title", "unknown")
        safe_title = "".join(c for c in title if c.isalnum() or c in " -_")[:50].strip()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"report_{safe_title}_{timestamp}.md"

    # Build report
    lines = []
    lines.append(f"# Translation Report")
    lines.append(f"")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**Model:** {model_used}")
    lines.append(f"**Profile:** {profile_name}")
    lines.append(f"")

    # Book metadata
    if metadata:
        lines.append(f"## Book Information")
        lines.append(f"")
        lines.append(f"| Field | Value |")
        lines.append(f"|-------|-------|")
        for key in ["title", "author", "format", "detected_language", "chapters", "total_paragraphs", "estimated_words"]:
            if key in metadata:
                lines.append(f"| {key.replace('_', ' ').title()} | {metadata[key]} |")
        lines.append(f"")

    # Translation stats
    if stats:
        lines.append(f"## Translation Statistics")
        lines.append(f"")
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")

        stat_fields = [
            ("total_requests", "API Calls"),
            ("chunk_counter", "Chunks Processed"),
            ("pass1_only_count", "Pass 1 Only"),
            ("full_3pass_count", "Full 3-Pass"),
            ("reviews_ok", "Reviews OK"),
            ("reviews_fixed", "Reviews Fixed"),
            ("glossary_terms", "Glossary Terms"),
            ("total_input_tokens", "Input Tokens"),
            ("total_output_tokens", "Output Tokens"),
            ("total_cache_read_tokens", "Cache Read Tokens"),
            ("total_cache_create_tokens", "Cache Create Tokens"),
        ]
        for key, label in stat_fields:
            if key in stats:
                val = stats[key]
                if isinstance(val, (int, float)) and val > 1000:
                    val = f"{val:,}"
                lines.append(f"| {label} | {val} |")

        if "cost_estimate" in stats:
            lines.append(f"| **Estimated Cost** | **${stats['cost_estimate']:.2f}** |")
        if "cost_without_cache" in stats:
            savings = stats["cost_without_cache"] - stats.get("cost_estimate", 0)
            if savings > 0.01:
                lines.append(f"| Cache Savings | ${savings:.2f} |")

        lines.append(f"")

    # Quality results
    if quality:
        lines.append(f"## Quality Assessment")
        lines.append(f"")

        if isinstance(quality, list):
            # Multiple spot checks
            all_scores = []
            for i, check in enumerate(quality):
                scores = check.get("scores", {})
                avg = check.get("average", 0)
                all_scores.append(avg)
                summary = check.get("summary", "N/A")
                lines.append(f"### Sample {i+1}")
                lines.append(f"")
                lines.append(f"- **Average:** {avg:.1f}/5")
                lines.append(f"- **Summary:** {summary}")
                issues = check.get("issues", [])
                if issues:
                    lines.append(f"- **Issues:** {', '.join(issues)}")
                lines.append(f"")

            if all_scores:
                overall = sum(all_scores) / len(all_scores)
                lines.append(f"### Overall Quality Score: {overall:.1f}/5")
                lines.append(f"")
                if overall >= 4.0:
                    lines.append(f"Quality is **good**. No retranslation recommended.")
                elif overall >= 3.0:
                    lines.append(f"Quality is **acceptable** but could be improved in specific areas.")
                else:
                    lines.append(f"Quality is **below threshold**. Consider retranslation with adjusted profile.")
        elif isinstance(quality, dict) and "scores" in quality:
            # Single spot check
            scores = quality.get("scores", {})
            lines.append(f"| Dimension | Score |")
            lines.append(f"|-----------|-------|")
            for dim, score in scores.items():
                lines.append(f"| {dim.title()} | {score}/5 |")
            lines.append(f"| **Average** | **{quality.get('average', 0):.1f}/5** |")
            lines.append(f"")
            if quality.get("summary"):
                lines.append(f"**Summary:** {quality['summary']}")
            issues = quality.get("issues", [])
            if issues:
                lines.append(f"")
                lines.append(f"**Issues found:**")
                for issue in issues:
                    lines.append(f"- {issue}")

        lines.append(f"")

    # Footer
    lines.append(f"---")
    lines.append(f"*Report generated by translation-orchestrator v0.1.0*")

    report_content = "\n".join(lines)

    # Write report
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    return json.dumps({
        "status": "generated",
        "path": output_path,
        "lines": len(lines),
        "has_stats": bool(stats),
        "has_quality": bool(quality),
    })
