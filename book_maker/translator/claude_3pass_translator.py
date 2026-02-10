"""
3-Pass Literary Translator with loadable genre profiles and prompt caching.
Plugs into bilingual_book_maker's existing architecture.

Architecture:
  Pass 1: TRANSLATE  — Full literary translation
  Pass 2: REVIEW     — Deep self-critique with extended thinking (style, accuracy,
                        glossary consistency, tone fidelity, protected nouns)
  Pass 3: REFINE     — Apply all corrections, produce polished final version

  Smart dispatch:
    - Short paragraphs (<min_review_chars): Pass 1 only (saves cost)
    - Long paragraphs: Full 3-pass
    - Batch mode (--block_size): Multiple paragraphs per API call

  Prompt caching (automatic):
    - System prompts are marked for caching via cache_control
    - First call costs +25% but all subsequent calls get 90% discount
    - For 1,300+ calls with the same prompt, saves ~$40-60 on Opus

  Genre profiles (JSON files) control:
    - Style instructions, protected nouns, seed glossary
    - Temperature per pass, review thresholds
    - Context/glossary update frequency

  IMPORTANT: Do NOT use --parallel-workers > 1.
  Glossary and context are shared state.
"""

import json
import os
import time
import atexit
from threading import Lock
from rich import print as rprint

from .base_translator import Base

# ─── Constants ────────────────────────────────────────────────────────────────

DEFAULT_MIN_REVIEW_CHARS = 300
DEFAULT_CONTEXT_INTERVAL = 15
DEFAULT_GLOSSARY_INTERVAL = 20
PARA_DELIMITER = "|||PARA|||"

# ─── Prompt Templates ────────────────────────────────────────────────────────
# Use {language} and {source_language} so they adapt to any language pair.
# Designed to be long and detailed — prompt caching makes this nearly free
# after the first call.

SYSTEM_TRANSLATE = """\
You are an expert literary translator specialising in {source_language} → {language} \
translation. Your translations are published-quality: natural, fluent, and faithful \
to the author's voice.

═══ STYLE INSTRUCTIONS ═══
{style_instructions}

═══ TRANSLATION RULES ═══
1. Output ONLY the {language} translation — no commentary, notes, or explanations
2. Translate COMPLETELY — never shorten, summarise, or omit any content
3. Preserve all HTML/XML tags exactly as they appear
4. Preserve the author's sentence structure and rhythm where natural in {language}
5. Translate idioms and expressions by meaning, not word-for-word
6. Maintain register: formal stays formal, colloquial stays colloquial
7. For dialogue, use natural spoken {language} appropriate to the character
8. Preserve intentional stylistic choices (short sentences for tension, \
long sentences for atmosphere, etc.)
{protected_nouns_section}
═══ GLOSSARY (established translations in this book) ═══
{glossary}

═══ NARRATIVE CONTEXT (story so far) ═══
{context}
{batch_instruction}"""

SYSTEM_REVIEW = """\
You are a senior literary translation editor reviewing a {source_language} → {language} \
translation. You have decades of experience with published literary translations.

═══ REVIEW CHECKLIST ═══
Examine the translation against the original on ALL of these axes:

1. COMPLETENESS — Is anything missing, added, or significantly altered?
2. ACCURACY — Are meanings preserved precisely? Any mistranslations?
3. PROTECTED NOUNS — Are any protected names/terms incorrectly translated? \
(These must NEVER be changed: {protected_nouns_list})
4. STYLE FIDELITY — Does the translation match the original's style?
   Check against these style instructions:
   {style_instructions}
5. TONE & ATMOSPHERE — Is the mood, register, and emotional weight preserved?
6. NATURALNESS — Does it read like native {language} prose, not "translationese"?
7. GLOSSARY CONSISTENCY — Do translated terms match the established glossary?
8. SENTENCE QUALITY — Are there awkward constructions, unnatural word order, \
or anglicisms (or source-language interference)?
{batch_review_note}
═══ GLOSSARY ═══
{glossary}

═══ OUTPUT FORMAT ═══
If the translation is excellent with no issues, respond with ONLY: QUALITY_OK

Otherwise, produce a numbered list. For each issue:
- LOCATION: the affected passage (quote briefly)
- PROBLEM: what is wrong and why
- SEVERITY: minor / moderate / critical
- FIX: the corrected {language} text"""

SYSTEM_REFINE = """\
You are a professional literary translator performing final revision of a \
{source_language} → {language} translation.

═══ INSTRUCTIONS ═══
1. Fix ALL issues identified in the review — every single one
2. Preserve the author's style, voice, and tone throughout
3. Protected proper nouns must NEVER be translated
4. Maintain all HTML/XML tags exactly as they appear
5. Output ONLY the corrected {language} translation — no notes or commentary
6. If the review says "QUALITY_OK", return the translation UNCHANGED
{batch_instruction}
═══ GLOSSARY ═══
{glossary}"""

SYSTEM_CONTEXT = """\
You are a literary translator's assistant maintaining a rolling narrative summary.

Produce a concise summary (max 4 sentences) capturing:
- Key characters present and their current state/emotions
- Current location and setting
- Plot developments and narrative momentum
- Overall mood/atmosphere

Write the summary in {language}. Respond ONLY with the summary."""

SYSTEM_GLOSSARY = """\
Extract important translated term pairs from the original/translation pair below.

Return a JSON object mapping source terms to {language} translations.
Include: character names, place names, recurring objects, technical terms, \
invented words, titles, and any terms that should stay consistent throughout the book.
Maximum 15 entries. Focus on terms that appear repeatedly.

Respond ONLY with a valid JSON object, no markdown fences or commentary."""


class Claude3Pass(Base):
    """
    3-pass literary translator with loadable genre profiles and prompt caching.
    Drop-in replacement for bilingual_book_maker's standard translators.
    """

    def __init__(
        self,
        key,
        language,
        api_base=None,
        prompt_template=None,
        prompt_sys_msg=None,
        temperature=1.0,
        context_flag=False,
        context_paragraph_limit=5,
        skip_review=False,
        model_name=None,
        source_lang=None,
        **kwargs,
    ) -> None:
        super().__init__(key, language)

        from anthropic import Anthropic
        self.client = Anthropic(base_url=api_base, api_key=key, timeout=180)

        self.model = model_name or "claude-sonnet-4-20250514"
        self.language = language or "German"
        self.source_language = self._resolve_source_lang(source_lang)

        # Profile (defaults, overridden by load_profile)
        self.profile_name = "Default"
        self.style_instructions = (
            "- Produce natural, fluent literary prose in the target language\n"
            "- Preserve the author's voice, tone, and style\n"
            "- Translate idioms by meaning, not word-for-word\n"
            "- Maintain sentence rhythm and pacing where possible\n"
            "- Use natural target-language sentence structures"
        )
        self.protected_nouns = []
        self.skip_review = skip_review

        # Temperatures
        self.temp_translate = 0.3
        self.temp_review = 0.4
        self.temp_refine = 0.2

        # Thresholds
        self.min_review_chars = DEFAULT_MIN_REVIEW_CHARS
        self.context_update_interval = DEFAULT_CONTEXT_INTERVAL
        self.glossary_update_interval = DEFAULT_GLOSSARY_INTERVAL

        # Rolling state
        self.glossary = {}
        self.context_summary = ""
        self.context_flag = context_flag
        self.context_paragraph_limit = context_paragraph_limit

        # Compatibility attrs for epub_loader parallel context mechanism
        self.context_list = []
        self.context_translated_list = []

        # Stats
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cache_read_tokens = 0
        self.total_cache_create_tokens = 0
        self.total_requests = 0
        self.pass1_only_count = 0
        self.full_3pass_count = 0
        self.reviews_ok = 0
        self.reviews_fixed = 0
        self.chunk_counter = 0
        self.glossary_extract_failures = 0

        self._glossary_lock = Lock()

        # Print final stats on exit
        atexit.register(self._print_final_stats)

    # ─── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _resolve_source_lang(source_lang):
        """Map language codes to full names for better prompts."""
        mapping = {
            "en": "English", "de": "German", "fr": "French", "es": "Spanish",
            "it": "Italian", "pt": "Portuguese", "nl": "Dutch", "ru": "Russian",
            "ja": "Japanese", "zh": "Chinese", "zh-hans": "Simplified Chinese",
            "zh-hant": "Traditional Chinese", "ko": "Korean", "pl": "Polish",
            "sv": "Swedish", "da": "Danish", "no": "Norwegian", "fi": "Finnish",
            "cs": "Czech", "hu": "Hungarian", "ro": "Romanian", "tr": "Turkish",
            "ar": "Arabic", "he": "Hebrew", "hi": "Hindi", "th": "Thai",
            "vi": "Vietnamese", "uk": "Ukrainian", "el": "Greek",
        }
        if not source_lang or source_lang == "auto":
            return "English"
        return mapping.get(source_lang.lower(), source_lang)

    # ─── Profile Loading ─────────────────────────────────────────────────

    def load_profile(self, profile_path):
        """Load a genre/style profile from a JSON file."""
        if not os.path.exists(profile_path):
            raise FileNotFoundError(f"Translation profile not found: {profile_path}")

        with open(profile_path, "r", encoding="utf-8") as f:
            profile = json.load(f)

        self.profile_name = profile.get("name", os.path.basename(profile_path))

        if "style_instructions" in profile:
            self.style_instructions = profile["style_instructions"]

        nouns = profile.get("protected_nouns", [])
        skip_prefixes = ("Names,", "Add ", "DELETE", "Character ", "One entry", "Delete ")
        self.protected_nouns = [
            n for n in nouns if not n.startswith(skip_prefixes) and len(n) < 100
        ]

        # Source language override from profile
        if "source_language" in profile:
            self.source_language = profile["source_language"]

        seed = profile.get("glossary_seed", {})
        seed.pop("_comment", None)
        self.glossary.update(seed)

        temps = profile.get("temperature", {})
        temps.pop("_comment", None)
        self.temp_translate = temps.get("translate", self.temp_translate)
        self.temp_review = temps.get("review", self.temp_review)
        self.temp_refine = temps.get("refine", self.temp_refine)

        self.min_review_chars = profile.get("min_review_chars", self.min_review_chars)
        self.context_update_interval = profile.get("context_update_interval", self.context_update_interval)
        self.glossary_update_interval = profile.get("glossary_update_interval", self.glossary_update_interval)

        rprint(f"  [bold green]Profile: {self.profile_name}[/bold green]")
        if self.protected_nouns:
            rprint(f"  Protected nouns: {len(self.protected_nouns)}")
        if self.glossary:
            rprint(f"  Seed glossary: {len(self.glossary)} terms")

    def rotate_key(self):
        pass

    def set_claude_model(self, model_name):
        self.model = model_name

    # ─── Main Entry Point ────────────────────────────────────────────────

    def translate(self, text):
        """Called by epub_loader per paragraph or per block."""
        self.chunk_counter += 1
        is_batch = "\n" in text.strip()

        if is_batch:
            return self._translate_batch(text)
        if len(text) < self.min_review_chars or self.skip_review:
            return self._translate_pass1_only(text)
        return self._translate_3pass(text)

    # ─── Translation Modes ───────────────────────────────────────────────

    def _translate_pass1_only(self, text):
        self.pass1_only_count += 1
        rprint(f"  [dim]#{self.chunk_counter} ({len(text)}c) P1[/dim]")
        translation = self._pass1(text)
        self._maybe_update_context_glossary(text, translation)
        return translation

    def _translate_3pass(self, text):
        self.full_3pass_count += 1
        rprint(f"  [cyan]#{self.chunk_counter} ({len(text)}c) 3-pass[/cyan]", end="")

        translation = self._pass1(text)
        rprint(f" [green]P1[/green]", end="")

        review = self._pass2(text, translation)
        if self._is_quality_ok(review):
            self.reviews_ok += 1
            rprint(f" [green]P2:OK[/green]")
            self._maybe_update_context_glossary(text, translation)
            return translation

        self.reviews_fixed += 1
        refined = self._pass3(text, translation, review)
        rprint(f" [yellow]P2:fix[/yellow] [green]P3[/green]")
        self._maybe_update_context_glossary(text, refined)
        return refined

    def _translate_batch(self, text):
        paragraphs = text.split("\n")
        para_count = len(paragraphs)
        total_chars = len(text)
        self.full_3pass_count += 1

        rprint(f"  [cyan]#{self.chunk_counter} BATCH ({para_count}p, {total_chars}c)[/cyan]", end="")

        delimited = f"\n{PARA_DELIMITER}\n".join(paragraphs)
        bi = (
            f"\n═══ BATCH MODE ═══\n"
            f"The input contains {para_count} paragraphs separated by {PARA_DELIMITER}\n"
            f"Separate translated paragraphs with {PARA_DELIMITER} as well.\n"
            f"Translate EVERY paragraph completely. The paragraph count MUST stay exactly {para_count}."
        )

        translation = self._pass1(delimited, batch_instruction=bi)
        rprint(f" [green]P1[/green]", end="")

        if not self.skip_review and total_chars >= self.min_review_chars:
            review = self._pass2(delimited, translation, is_batch=True)
            if self._is_quality_ok(review):
                self.reviews_ok += 1
                rprint(f" [green]P2:OK[/green]")
            else:
                self.reviews_fixed += 1
                translation = self._pass3(delimited, translation, review, batch_instruction=bi)
                rprint(f" [yellow]P2:fix[/yellow] [green]P3[/green]")
        else:
            rprint(f" [dim]skip review[/dim]")

        # Reassemble paragraphs
        parts = [p.strip().replace("\n", " ") for p in translation.split(PARA_DELIMITER) if p.strip()]

        if len(parts) == para_count:
            result = "\n".join(parts)
        elif len(parts) > para_count:
            merged = parts[:para_count - 1] + [" ".join(parts[para_count - 1:])]
            result = "\n".join(merged)
            rprint(f"  [dim](merged {len(parts)}→{para_count} paras)[/dim]")
        else:
            padded = parts + paragraphs[len(parts):]
            result = "\n".join(padded[:para_count])
            rprint(f"  [dim](padded {len(parts)}→{para_count} paras)[/dim]")

        self._maybe_update_context_glossary(text, result)
        if self.chunk_counter % 10 == 0:
            self._print_stats()
        return result

    @staticmethod
    def _is_quality_ok(review):
        return any(tag in review for tag in ("QUALITY_OK", "QUALITAET_OK", "QUALITÄT_OK"))

    # ─── Prompt Builders ─────────────────────────────────────────────────

    def _protected_nouns_section(self):
        if not self.protected_nouns:
            return ""
        nouns = ", ".join(self.protected_nouns[:60])
        return (
            f"\n═══ PROTECTED PROPER NOUNS — NEVER TRANSLATE THESE ═══\n"
            f"{nouns}\n"
            f"These names/terms must appear in the translation EXACTLY as written above.\n"
        )

    def _protected_nouns_list_short(self):
        """Short list for review prompt."""
        if not self.protected_nouns:
            return "(none)"
        return ", ".join(self.protected_nouns[:30])

    def _pass1(self, text, batch_instruction=""):
        system = SYSTEM_TRANSLATE.format(
            source_language=self.source_language,
            language=self.language,
            style_instructions=self.style_instructions,
            protected_nouns_section=self._protected_nouns_section(),
            glossary=self._format_glossary() or "(none yet — beginning of book)",
            context=self.context_summary or "(beginning of text)",
            batch_instruction=batch_instruction,
        )
        user = f"Translate the following {self.source_language} text into {self.language}:\n\n{text}"
        return self._api_call(system, user, self.temp_translate)

    def _pass2(self, original, translation, is_batch=False):
        batch_note = ""
        if is_batch:
            batch_note = (
                f"\nNOTE: The text contains {PARA_DELIMITER} paragraph delimiters. "
                f"Treat each delimited section as a separate paragraph for review."
            )
        system = SYSTEM_REVIEW.format(
            source_language=self.source_language,
            language=self.language,
            style_instructions=self.style_instructions,
            protected_nouns_list=self._protected_nouns_list_short(),
            glossary=self._format_glossary() or "(empty)",
            batch_review_note=batch_note,
        )
        user = f"ORIGINAL ({self.source_language}):\n{original}\n\nTRANSLATION ({self.language}):\n{translation}"
        return self._api_call(system, user, self.temp_review)

    def _pass3(self, original, translation, review, batch_instruction=""):
        system = SYSTEM_REFINE.format(
            source_language=self.source_language,
            language=self.language,
            glossary=self._format_glossary() or "(empty)",
            batch_instruction=batch_instruction,
        )
        user = (
            f"ORIGINAL ({self.source_language}):\n{original}\n\n"
            f"CURRENT TRANSLATION ({self.language}):\n{translation}\n\n"
            f"EDITOR REVIEW:\n{review}\n\n"
            f"Produce the corrected final {self.language} translation:"
        )
        return self._api_call(system, user, self.temp_refine)

    # ─── Context & Glossary ──────────────────────────────────────────────

    def _maybe_update_context_glossary(self, original, translation):
        if self.context_flag and self.chunk_counter % self.context_update_interval == 0:
            try:
                prev = self.context_summary
                msg = (
                    f"Previous summary:\n{prev}\n\n"
                    f"New original text:\n{original[:1500]}\n\n"
                    f"New translation:\n{translation[:1500]}"
                ) if prev else f"Original:\n{original[:2000]}\n\nTranslation:\n{translation[:2000]}"
                self.context_summary = self._api_call(
                    SYSTEM_CONTEXT.format(language=self.language),
                    msg, 0.3, max_tokens=512, use_cache=False,
                )
            except Exception as e:
                rprint(f"  [dim](context update failed: {e})[/dim]")

        if self.chunk_counter % self.glossary_update_interval == 0:
            try:
                msg = (
                    f"ORIGINAL ({self.source_language}):\n{original[:2000]}\n\n"
                    f"TRANSLATION ({self.language}):\n{translation[:2000]}"
                )
                resp = self._api_call(
                    SYSTEM_GLOSSARY.format(language=self.language),
                    msg, 0.1, max_tokens=1024, use_cache=False,
                )
                resp = resp.strip()
                if resp.startswith("```"):
                    resp = resp.split("\n", 1)[1].rsplit("```", 1)[0]
                new_terms = json.loads(resp)
                if isinstance(new_terms, dict):
                    # Filter out junk entries
                    valid = {k: v for k, v in new_terms.items()
                             if isinstance(k, str) and isinstance(v, str)
                             and len(k) < 100 and len(v) < 200
                             and not k.startswith("_")}
                    if valid:
                        with self._glossary_lock:
                            self.glossary.update(valid)
                        rprint(f"  [dim]+{len(valid)} glossary terms (total: {len(self.glossary)})[/dim]")
            except json.JSONDecodeError as e:
                self.glossary_extract_failures += 1
                if self.glossary_extract_failures <= 5:
                    rprint(f"  [dim](glossary JSON parse failed: {e})[/dim]")
                elif self.glossary_extract_failures == 6:
                    rprint(f"  [dim](suppressing further glossary warnings)[/dim]")
            except Exception as e:
                self.glossary_extract_failures += 1
                if self.glossary_extract_failures <= 3:
                    rprint(f"  [dim](glossary extraction failed: {e})[/dim]")

    def _format_glossary(self):
        with self._glossary_lock:
            if not self.glossary:
                return ""
            lines = [f"  {src} → {tgt}" for src, tgt in sorted(self.glossary.items())
                     if not src.startswith("_")]
        return "\n".join(lines[:60])

    # ─── API Client with Prompt Caching ──────────────────────────────────

    def _api_call(self, system, user, temperature, max_tokens=8192,
                  retries=5, use_cache=True):
        """
        Make an API call with automatic prompt caching.

        Prompt caching: the system prompt is marked with cache_control so that
        repeated calls with the same system prompt get 90% input token discount.
        First call: +25% cost for cache write. All subsequent: -90% for cache read.
        For 1,300+ translate() calls, this saves ~$40-60 on Opus.
        """
        # Build system message — with or without cache control
        if use_cache:
            system_msg = [{
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }]
        else:
            system_msg = system

        for attempt in range(retries):
            try:
                kwargs = {
                    "model": self.model,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "system": system_msg,
                    "messages": [{"role": "user", "content": user}],
                }

                response = self.client.messages.create(**kwargs)

                # Track tokens
                usage = response.usage
                self.total_input_tokens += usage.input_tokens
                self.total_output_tokens += usage.output_tokens
                self.total_cache_read_tokens += getattr(usage, "cache_read_input_tokens", 0)
                self.total_cache_create_tokens += getattr(usage, "cache_creation_input_tokens", 0)
                self.total_requests += 1

                return "".join(b.text for b in response.content if b.type == "text")

            except Exception as e:
                err = type(e).__name__
                if attempt < retries - 1:
                    wait = min(60, 2 ** attempt * (5 if "RateLimit" in err or "rate" in str(e).lower() else 3))
                    rprint(f"  [red]{err}, retry in {wait}s[/red]")
                    time.sleep(wait)
                else:
                    raise
        raise RuntimeError(f"Failed after {retries} retries")

    # ─── Stats ───────────────────────────────────────────────────────────

    def _cost_estimate(self):
        pricing = {
            "claude-opus-4-20250514": {"input": 15.0, "output": 75.0, "cache_read": 1.5, "cache_write": 18.75},
            "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0, "cache_read": 0.30, "cache_write": 3.75},
        }
        p = pricing.get(self.model, pricing["claude-sonnet-4-20250514"])

        # Tokens that hit the cache don't count as regular input
        uncached_input = self.total_input_tokens - self.total_cache_read_tokens - self.total_cache_create_tokens
        cost = (
            max(0, uncached_input) / 1e6 * p["input"]
            + self.total_output_tokens / 1e6 * p["output"]
            + self.total_cache_read_tokens / 1e6 * p["cache_read"]
            + self.total_cache_create_tokens / 1e6 * p["cache_write"]
        )
        # What it would have cost without caching
        cost_no_cache = (
            self.total_input_tokens / 1e6 * p["input"]
            + self.total_output_tokens / 1e6 * p["output"]
        )
        return cost, cost_no_cache

    def _print_stats(self):
        cost, cost_no_cache = self._cost_estimate()
        saved = cost_no_cache - cost

        rprint(f"\n[bold blue]─── {self.profile_name} │ chunk {self.chunk_counter} ───[/bold blue]")
        rprint(f"  API calls: {self.total_requests:,} │ {self.total_input_tokens:,} in / {self.total_output_tokens:,} out")
        if self.total_cache_read_tokens > 0:
            rprint(f"  Cache: {self.total_cache_read_tokens:,} read / {self.total_cache_create_tokens:,} write (saved ${saved:.2f})")
        rprint(f"  P1-only: {self.pass1_only_count} │ 3-pass: {self.full_3pass_count} │ OK: {self.reviews_ok} │ fixed: {self.reviews_fixed}")
        rprint(f"  Glossary: {len(self.glossary)} terms │ Cost: ${cost:.2f}")
        rprint(f"[bold blue]{'─' * 50}[/bold blue]\n")

    def _print_final_stats(self):
        if self.total_requests == 0:
            return
        cost, cost_no_cache = self._cost_estimate()
        saved = cost_no_cache - cost

        rprint(f"\n[bold green]{'═' * 55}[/bold green]")
        rprint(f"[bold green]  TRANSLATION COMPLETE — {self.profile_name}[/bold green]")
        rprint(f"[bold green]{'═' * 55}[/bold green]")
        rprint(f"  Model: {self.model}")
        rprint(f"  Language: {self.source_language} → {self.language}")
        rprint(f"  Chunks translated: {self.chunk_counter}")
        rprint(f"  API calls: {self.total_requests:,}")
        rprint(f"  Tokens: {self.total_input_tokens:,} input / {self.total_output_tokens:,} output")
        if self.total_cache_read_tokens > 0:
            pct = self.total_cache_read_tokens / max(1, self.total_input_tokens) * 100
            rprint(f"  Prompt cache hit rate: {pct:.0f}%")
            rprint(f"  Cache savings: ${saved:.2f}")
        rprint(f"  Pass 1 only: {self.pass1_only_count} │ Full 3-pass: {self.full_3pass_count}")
        rprint(f"  Reviews OK: {self.reviews_ok} │ Reviews with fixes: {self.reviews_fixed}")
        rprint(f"  Glossary terms: {len(self.glossary)}")
        if self.glossary_extract_failures > 0:
            rprint(f"  Glossary extraction failures: {self.glossary_extract_failures}")
        rprint(f"  [bold]Total cost: ${cost:.2f}[/bold]")
        if saved > 1:
            rprint(f"  (Without prompt caching: ${cost_no_cache:.2f})")
        rprint(f"[bold green]{'═' * 55}[/bold green]\n")
