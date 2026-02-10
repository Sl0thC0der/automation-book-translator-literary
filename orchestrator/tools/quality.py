"""Quality review tools — extract paragraph pairs and spot-check translation quality."""

import os
import json
import random


def extract_paragraphs(
    original_path: str,
    translated_path: str,
    sample_count: int = 10,
    strategy: str = "evenly_spaced",
) -> str:
    """Extract original+translated paragraph pairs for quality review.

    Args:
        original_path: Path to original epub
        translated_path: Path to translated/bilingual epub
        sample_count: Number of paragraph pairs to extract (default: 10)
        strategy: Sampling strategy: 'evenly_spaced', 'random', or 'first' (default: evenly_spaced)

    Returns:
        JSON string with matched paragraph pairs.
    """
    from book_maker.loader.epub_loader import EPUBBookLoader

    if not os.path.exists(original_path):
        return json.dumps({"error": f"Original file not found: {original_path}"})
    if not os.path.exists(translated_path):
        return json.dumps({"error": f"Translated file not found: {translated_path}"})

    orig_data = EPUBBookLoader.extract_chapter_paragraphs(original_path)
    trans_data = EPUBBookLoader.extract_chapter_paragraphs(translated_path)

    # Build lookup by chapter filename
    trans_by_file = {ch["filename"]: ch["paragraphs"] for ch in trans_data["chapters"]}

    # Collect all matchable pairs
    all_pairs = []
    for ch in orig_data["chapters"]:
        trans_paras = trans_by_file.get(ch["filename"], [])
        for i, orig_para in enumerate(ch["paragraphs"]):
            if i < len(trans_paras):
                all_pairs.append({
                    "chapter": ch["filename"],
                    "index": i,
                    "original": orig_para,
                    "translated": trans_paras[i],
                })

    if not all_pairs:
        return json.dumps({"error": "No matching paragraph pairs found"})

    # Sample
    if strategy == "random":
        selected = random.sample(all_pairs, min(sample_count, len(all_pairs)))
    elif strategy == "first":
        selected = all_pairs[:sample_count]
    else:  # evenly_spaced
        step = max(1, len(all_pairs) // sample_count)
        selected = [all_pairs[i] for i in range(0, len(all_pairs), step)][:sample_count]

    return json.dumps({
        "pairs": selected,
        "total_available": len(all_pairs),
        "sampled": len(selected),
        "strategy": strategy,
    }, ensure_ascii=False, indent=2)


def quality_spot_check(
    original_text: str,
    translated_text: str,
    source_language: str = "English",
    target_language: str = "German",
    style_instructions: str = "",
    protected_nouns: str = "",
) -> str:
    """Evaluate translation quality of a paragraph pair using Claude.

    Uses Sonnet for cost efficiency. Returns structured quality scores.

    Args:
        original_text: Original text
        translated_text: Translated text
        source_language: Source language name
        target_language: Target language name
        style_instructions: Style instructions for evaluation context
        protected_nouns: Comma-separated protected nouns

    Returns:
        JSON string with quality scores and issues.
    """
    api_key = os.environ.get("BBM_CLAUDE_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return json.dumps({"error": "No API key found. Set ANTHROPIC_API_KEY or BBM_CLAUDE_API_KEY."})

    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)

    system_prompt = f"""\
You are a professional translation quality evaluator assessing {source_language} → {target_language} translations.

Rate the translation on these 5 dimensions (1-5 scale, 5 = excellent):
1. ACCURACY — Faithfulness to meaning
2. FLUENCY — Natural target-language prose
3. STYLE — Preservation of author's voice/tone
4. COMPLETENESS — Nothing missing or added
5. TERMINOLOGY — Correct use of terms/names

{f"Style context: {style_instructions}" if style_instructions else ""}
{f"Protected nouns (must not be translated): {protected_nouns}" if protected_nouns else ""}

Respond with ONLY a valid JSON object:
{{
  "scores": {{
    "accuracy": <1-5>,
    "fluency": <1-5>,
    "style": <1-5>,
    "completeness": <1-5>,
    "terminology": <1-5>
  }},
  "average": <float>,
  "issues": ["issue 1", "issue 2"],
  "summary": "One sentence overall assessment"
}}"""

    user_msg = f"ORIGINAL ({source_language}):\n{original_text}\n\nTRANSLATION ({target_language}):\n{translated_text}"

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            temperature=0.2,
            system=system_prompt,
            messages=[{"role": "user", "content": user_msg}],
        )

        result_text = "".join(b.text for b in response.content if b.type == "text").strip()

        # Parse JSON from response
        if result_text.startswith("```"):
            result_text = result_text.split("\n", 1)[1].rsplit("```", 1)[0]

        result = json.loads(result_text)
        result["tokens_used"] = {
            "input": response.usage.input_tokens,
            "output": response.usage.output_tokens,
        }
        return json.dumps(result, ensure_ascii=False, indent=2)

    except json.JSONDecodeError:
        return json.dumps({
            "error": "Failed to parse quality evaluation response",
            "raw_response": result_text[:500],
        })
    except Exception as e:
        return json.dumps({"error": str(e), "type": type(e).__name__})
