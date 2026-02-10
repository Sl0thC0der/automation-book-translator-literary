"""Book analysis tool — extract metadata, detect language, sample text."""

import os
import json
from pathlib import Path


def analyze_book(book_path: str, sample_count: int = 5) -> str:
    """Extract metadata, detect language, and sample text from a book.

    Args:
        book_path: Path to the book file (epub, txt, pdf)
        sample_count: Number of sample paragraphs to extract (default: 5)

    Returns:
        JSON string with book metadata and analysis.
    """
    if not os.path.exists(book_path):
        return json.dumps({"error": f"File not found: {book_path}"})

    ext = Path(book_path).suffix.lower()
    result = {
        "file": book_path,
        "format": ext.lstrip("."),
        "file_size_bytes": os.path.getsize(book_path),
    }

    if ext == ".epub":
        result.update(_analyze_epub(book_path, sample_count))
    elif ext == ".txt":
        result.update(_analyze_txt(book_path, sample_count))
    elif ext == ".pdf":
        result.update(_analyze_pdf(book_path, sample_count))
    else:
        result["error"] = f"Unsupported format: {ext}"

    return json.dumps(result, ensure_ascii=False, indent=2)


def _analyze_epub(epub_path: str, sample_count: int) -> dict:
    """Analyze an EPUB file."""
    from ebooklib import epub, ITEM_DOCUMENT
    from book_maker.loader.epub_loader import EPUBBookLoader

    book = epub.read_epub(epub_path)

    # Extract metadata
    title = ""
    author = ""
    language = ""
    for ns, metas in book.metadata.items():
        if isinstance(metas, dict):
            for name, values in metas.items():
                for val in values:
                    v = val[0] if isinstance(val, tuple) else val
                    if name == "title" and not title:
                        title = str(v)
                    elif name == "creator" and not author:
                        author = str(v)
                    elif name == "language" and not language:
                        language = str(v)

    # Extract chapter info
    data = EPUBBookLoader.extract_chapter_paragraphs(epub_path)
    chapters = data["chapters"]
    total_paragraphs = data["total_paragraphs"]

    # Estimate word count
    total_words = 0
    all_paragraphs = []
    for ch in chapters:
        for p in ch["paragraphs"]:
            total_words += len(p.split())
            all_paragraphs.append(p)

    # Sample paragraphs (evenly spaced)
    samples = []
    if all_paragraphs:
        step = max(1, len(all_paragraphs) // sample_count)
        for i in range(0, len(all_paragraphs), step):
            if len(samples) >= sample_count:
                break
            samples.append(all_paragraphs[i][:500])

    # Detect source language
    source_language = "unknown"
    try:
        from langdetect import detect
        sample_text = " ".join(all_paragraphs[:20])
        if sample_text.strip():
            source_language = detect(sample_text)
    except Exception:
        pass

    # Cost estimates (rough)
    cost_estimates = _estimate_costs(total_words)

    return {
        "title": title,
        "author": author,
        "epub_language": language,
        "detected_language": source_language,
        "chapters": len(chapters),
        "chapter_names": [ch["filename"] for ch in chapters],
        "total_paragraphs": total_paragraphs,
        "estimated_words": total_words,
        "samples": samples,
        "cost_estimates": cost_estimates,
    }


def _analyze_txt(txt_path: str, sample_count: int) -> dict:
    """Analyze a TXT file."""
    with open(txt_path, "r", encoding="utf-8") as f:
        content = f.read()

    lines = [l.strip() for l in content.split("\n") if l.strip()]
    total_words = sum(len(l.split()) for l in lines)

    samples = []
    if lines:
        step = max(1, len(lines) // sample_count)
        for i in range(0, len(lines), step):
            if len(samples) >= sample_count:
                break
            samples.append(lines[i][:500])

    source_language = "unknown"
    try:
        from langdetect import detect
        sample_text = " ".join(lines[:20])
        if sample_text.strip():
            source_language = detect(sample_text)
    except Exception:
        pass

    return {
        "title": Path(txt_path).stem,
        "author": "",
        "detected_language": source_language,
        "chapters": 1,
        "total_paragraphs": len(lines),
        "estimated_words": total_words,
        "samples": samples,
        "cost_estimates": _estimate_costs(total_words),
    }


def _analyze_pdf(pdf_path: str, sample_count: int) -> dict:
    """Analyze a PDF file."""
    try:
        import fitz
    except ImportError:
        return {"error": "PyMuPDF (fitz) not installed. Install with: pip install PyMuPDF"}

    doc = fitz.open(pdf_path)
    all_text = []
    for page in doc:
        all_text.append(page.get_text())
    doc.close()

    lines = [l.strip() for l in "\n".join(all_text).split("\n") if l.strip()]
    total_words = sum(len(l.split()) for l in lines)

    samples = []
    if lines:
        step = max(1, len(lines) // sample_count)
        for i in range(0, len(lines), step):
            if len(samples) >= sample_count:
                break
            samples.append(lines[i][:500])

    source_language = "unknown"
    try:
        from langdetect import detect
        sample_text = " ".join(lines[:20])
        if sample_text.strip():
            source_language = detect(sample_text)
    except Exception:
        pass

    return {
        "title": Path(pdf_path).stem,
        "author": "",
        "detected_language": source_language,
        "pages": len(all_text),
        "total_paragraphs": len(lines),
        "estimated_words": total_words,
        "samples": samples,
        "cost_estimates": _estimate_costs(total_words),
    }


def _estimate_costs(total_words: int) -> dict:
    """Rough cost estimates based on word count."""
    # ~1.3 tokens per word, ~5000 paragraphs per 100k words
    paragraphs_est = max(1, total_words // 20)

    # With block_size (recommended): ~1 API call per 6 paragraphs, 2-3 calls per batch
    batches = max(1, paragraphs_est // 6)
    api_calls_block = batches * 2.5

    # Rough token estimates per API call
    input_tokens_per_call = 3000
    output_tokens_per_call = 1500

    total_input = int(api_calls_block * input_tokens_per_call)
    total_output = int(api_calls_block * output_tokens_per_call)

    sonnet_cost = total_input / 1e6 * 3.0 + total_output / 1e6 * 15.0
    opus_cost = total_input / 1e6 * 15.0 + total_output / 1e6 * 75.0

    # Cache discount ~60%
    sonnet_cached = sonnet_cost * 0.4
    opus_cached = opus_cost * 0.4

    return {
        "estimated_api_calls": int(api_calls_block),
        "sonnet_no_cache": f"${sonnet_cost:.2f}",
        "sonnet_with_cache": f"${sonnet_cached:.2f}",
        "opus_no_cache": f"${opus_cost:.2f}",
        "opus_with_cache": f"${opus_cached:.2f}",
        "recommendation": "sonnet" if total_words < 50000 else "sonnet (use opus for literary fiction)",
    }
