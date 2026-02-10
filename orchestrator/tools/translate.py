"""Translation tool — runs 3-pass literary translation directly via Python API."""

import os
import json
import asyncio
from dataclasses import asdict
from pathlib import Path


def run_translation(
    book_path: str,
    language: str = "de",
    model: str = "3pass-sonnet",
    profile_path: str = "",
    use_context: bool = True,
    skip_review: bool = False,
    test_mode: bool = False,
    test_num: int = 5,
    block_size: int = 1500,
    resume: bool = False,
    source_lang: str = "auto",
) -> str:
    """Run 3-pass literary translation on a book.

    Calls the translator directly as a Python library (not subprocess).

    Args:
        book_path: Path to the book file (epub, txt, pdf)
        language: Target language code (default: de)
        model: Model variant: 3pass-sonnet or 3pass-opus (default: 3pass-sonnet)
        profile_path: Path to translation profile JSON (optional)
        use_context: Enable rolling context summary (default: True)
        skip_review: Skip review pass for speed (default: False)
        test_mode: Only translate a few paragraphs (default: False)
        test_num: Number of test paragraphs (default: 5)
        block_size: Batch size in tokens (default: 1500, 0 to disable)
        resume: Resume interrupted translation (default: False)
        source_lang: Source language code (default: auto)

    Returns:
        JSON string with translation results and stats.
    """
    if not os.path.exists(book_path):
        return json.dumps({"error": f"File not found: {book_path}"})

    ext = Path(book_path).suffix.lower()
    if ext not in (".epub", ".txt", ".pdf"):
        return json.dumps({"error": f"Unsupported format: {ext}"})

    # Resolve API key
    api_key = os.environ.get("BBM_CLAUDE_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return json.dumps({"error": "No API key found. Set ANTHROPIC_API_KEY or BBM_CLAUDE_API_KEY."})

    # Resolve model
    model_id_map = {
        "3pass-opus": "claude-opus-4-20250514",
        "3pass-sonnet": "claude-sonnet-4-20250514",
        "3pass": "claude-sonnet-4-20250514",
    }
    claude_model = model_id_map.get(model, "claude-sonnet-4-20250514")

    # Resolve language name
    lang_map = {
        "de": "German", "en": "English", "fr": "French", "es": "Spanish",
        "it": "Italian", "pt": "Portuguese", "nl": "Dutch", "ru": "Russian",
        "ja": "Japanese", "zh": "Chinese", "ko": "Korean", "pl": "Polish",
    }
    language_name = lang_map.get(language.lower(), language)

    try:
        return _run_translation_sync(
            book_path=book_path,
            ext=ext,
            api_key=api_key,
            claude_model=claude_model,
            language_name=language_name,
            profile_path=profile_path,
            use_context=use_context,
            skip_review=skip_review,
            test_mode=test_mode,
            test_num=test_num,
            block_size=block_size,
            resume=resume,
            source_lang=source_lang,
        )
    except Exception as e:
        return json.dumps({"error": str(e), "type": type(e).__name__})


def _run_translation_sync(
    book_path, ext, api_key, claude_model, language_name,
    profile_path, use_context, skip_review, test_mode,
    test_num, block_size, resume, source_lang,
) -> str:
    """Run translation synchronously."""
    from book_maker.translator.claude_3pass_translator import Claude3Pass
    from book_maker.utils import prompt_config_to_kwargs

    # Track progress events
    progress_events = []
    chunk_results = []

    # Create translator instance
    translator = Claude3Pass(
        key=api_key,
        language=language_name,
        context_flag=use_context,
        skip_review=skip_review,
        model_name=claude_model,
        source_lang=source_lang,
    )

    # Load profile if specified
    if profile_path and os.path.exists(profile_path):
        translator.load_profile(profile_path)

    # Register hooks for progress tracking
    def on_chunk(event):
        chunk_results.append({
            "chunk": event.chunk_number,
            "passes": event.passes_used,
            "quality_ok": event.quality_ok,
            "is_batch": event.is_batch,
            "para_count": event.paragraph_count,
        })

    translator.on("on_chunk_complete", on_chunk)

    if ext == ".epub":
        output_path = _translate_epub(
            book_path, translator, language_name, use_context,
            test_mode, test_num, block_size, resume, source_lang,
            progress_events,
        )
    elif ext == ".txt":
        output_path = _translate_txt(
            book_path, translator, language_name,
            test_mode, test_num,
        )
    else:
        return json.dumps({"error": f"Direct translation not yet supported for {ext}. Use epub or txt."})

    # Get final stats
    stats = translator.get_stats()

    return json.dumps({
        "status": "completed",
        "output_path": output_path,
        "stats": asdict(stats),
        "chunks_processed": len(chunk_results),
        "model": claude_model,
        "profile": translator.profile_name,
    }, ensure_ascii=False, indent=2)


def _translate_epub(
    book_path, translator, language_name, use_context,
    test_mode, test_num, block_size, resume, source_lang,
    progress_events,
) -> str:
    """Run epub translation using the loader."""
    from book_maker.loader.epub_loader import EPUBBookLoader

    # Progress callback for the loader
    def progress_cb(event_type, data):
        progress_events.append({"event": event_type, **data})

    # EPUBBookLoader expects a model factory (class), not an instance.
    # We wrap our pre-configured translator in a factory that returns it.
    class TranslatorFactory:
        """Wraps a pre-built translator to satisfy EPUBBookLoader's model(key, lang, ...) call."""
        def __init__(self, translator_instance):
            self._instance = translator_instance

        def __call__(self, key, language, **kwargs):
            return self._instance

    factory = TranslatorFactory(translator)

    loader = EPUBBookLoader(
        epub_name=book_path,
        model=factory,
        key="unused",  # key already in translator
        resume=resume,
        language=language_name,
        is_test=test_mode,
        test_num=test_num,
        single_translate=True,
        context_flag=use_context,
        source_lang=source_lang,
        progress_callback=progress_cb,
    )

    # Set block_size
    if block_size > 0:
        loader.block_size = block_size

    loader.make_bilingual_book()

    name, _ = os.path.splitext(book_path)
    return f"{name}_bilingual.epub"


def _translate_txt(book_path, translator, language_name, test_mode, test_num) -> str:
    """Simple TXT translation — translate line by line."""
    with open(book_path, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f.readlines() if l.strip()]

    if test_mode:
        lines = lines[:test_num]

    translated = []
    for line in lines:
        result = translator.translate(line)
        translated.append(result)

    name, _ = os.path.splitext(book_path)
    output_path = f"{name}_bilingual.txt"

    with open(output_path, "w", encoding="utf-8") as f:
        for orig, trans in zip(lines, translated):
            f.write(f"{orig}\n{trans}\n\n")

    return output_path
