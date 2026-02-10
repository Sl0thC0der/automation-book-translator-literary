"""Translation orchestrator using Claude Agent SDK.

Manages the full translation workflow:
  1. Analyze book (metadata, language, genre)
  2. Select/create translation profile
  3. Test translation (5 paragraphs)
  4. Full translation
  5. Quality spot-check
  6. Generate report
"""

import asyncio
import json
import os
from pathlib import Path

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AgentDefinition,
    AssistantMessage,
    TextBlock,
)

from .tools import create_mcp_server, TOOL_NAMES


# ─── System Prompt ────────────────────────────────────────────────────────────

ORCHESTRATOR_SYSTEM_PROMPT = """\
You are a literary translation orchestrator. You manage the complete workflow \
for translating books using 3-pass literary translation (translate → review → refine).

You have access to tools for:
- Analyzing books (metadata, language detection, word count)
- Managing translation profiles (list, create, recommend)
- Running translations (test and full)
- Quality checking translations (extract pairs, spot-check)
- Generating reports

## Workflow

Follow this sequence unless the user overrides specific steps:

1. **Analyze** the book: detect language, count chapters/words, estimate cost
2. **Select profile**: check existing profiles, recommend or create one
3. **Test translate**: run 5 paragraphs to verify quality
4. **Full translate**: run the complete book
5. **Quality check**: spot-check 10-20 paragraph pairs
6. **Report**: generate a quality/cost report

## Important Rules

- Always analyze the book first to detect source language
- When creating profiles, write style_instructions in the TARGET language
- Use test_mode=true before full translation to catch issues early
- For quality checks, use evenly_spaced strategy for representative sampling
- If quality score < 4.0, report issues and recommend profile adjustments
- Track costs throughout — report total at the end
- Prefer 3pass-sonnet for most books; recommend opus only for literary fiction

## Cost Awareness

Sonnet: ~$3/100k input, ~$15/100k output (with cache: ~60% discount)
Opus: ~$15/100k input, ~$75/100k output (with cache: ~60% discount)

A 100k-word book with block_size=1500:
- Sonnet: ~$10-15 (with cache)
- Opus: ~$50-70 (with cache)
"""


# ─── Subagent Definitions ────────────────────────────────────────────────────

def _get_agents():
    """Define subagents for specialized tasks."""
    return {
        "book-analyzer": AgentDefinition(
            description="Analyze a book file to extract metadata, detect language and genre, and recommend a translation model. Use this agent when you need to understand the book before translation.",
            prompt="""\
You are a book analysis specialist. When given a book file:
1. Use analyze_book to extract metadata, detect language, and sample text
2. Use list_profiles to see available translation profiles
3. Analyze the samples to determine the genre/style
4. Recommend: model (sonnet vs opus), existing profile or suggest creating one
5. Report your findings clearly with cost estimates

Be concise and actionable in your recommendations.""",
            tools=[
                "mcp__translation-orchestrator__analyze_book",
                "mcp__translation-orchestrator__list_profiles",
            ],
            model="sonnet",
        ),
        "profile-creator": AgentDefinition(
            description="Create or recommend translation profiles. Use when you need to set up a new profile for a specific book genre or style.",
            prompt="""\
You are a translation profile specialist. Your job is to:
1. Review available profiles with list_profiles
2. If an existing profile matches, recommend it
3. If not, create a new profile with create_profile

When creating profiles:
- Write style_instructions in the TARGET language (e.g., German instructions for DE translations)
- Add protected nouns for character names, place names, and key terms
- Set appropriate temperatures (lower = more literal, higher = more creative)
- For literary fiction: temp_translate=0.3, temp_review=0.4, temp_refine=0.2
- For non-fiction: temp_translate=0.2, temp_review=0.3, temp_refine=0.15

Be thorough in setting protected nouns from the book's character/place names.""",
            tools=[
                "mcp__translation-orchestrator__list_profiles",
                "mcp__translation-orchestrator__create_profile",
            ],
            model="sonnet",
        ),
        "quality-reviewer": AgentDefinition(
            description="Review translation quality by spot-checking paragraph pairs. Use after translation is complete to assess quality.",
            prompt="""\
You are a translation quality reviewer. Your job is to:
1. Use extract_paragraphs to get sample pairs from original and translated books
2. Use quality_spot_check on each pair to evaluate quality
3. Identify systemic issues (consistent errors across samples)
4. Provide an overall quality score and detailed feedback

Check at least 10 samples using evenly_spaced strategy for representativeness.
Report both individual scores and overall average.
Flag any samples scoring below 3.0 as needing attention.""",
            tools=[
                "mcp__translation-orchestrator__extract_paragraphs",
                "mcp__translation-orchestrator__quality_spot_check",
            ],
            model="sonnet",
        ),
    }


# ─── Orchestrator Class ─────────────────────────────────────────────────────

class TranslationOrchestrator:
    """High-level orchestrator that drives the translation workflow."""

    def __init__(
        self,
        book_path: str,
        language: str = "de",
        model: str = "auto",
        profile_path: str = "",
        source_lang: str = "auto",
        profiles_dir: str = "examples/profiles",
        report_dir: str = ".",
        skip_analysis: bool = False,
        skip_test: bool = False,
        skip_quality_check: bool = False,
        resume: bool = False,
        verbose: bool = False,
    ):
        self.book_path = book_path
        self.language = language
        self.model = model
        self.profile_path = profile_path
        self.source_lang = source_lang
        self.profiles_dir = profiles_dir
        self.report_dir = report_dir
        self.skip_analysis = skip_analysis
        self.skip_test = skip_test
        self.skip_quality_check = skip_quality_check
        self.resume = resume
        self.verbose = verbose

    async def run(self):
        """Execute the full orchestration workflow."""
        mcp_server = create_mcp_server()

        options = ClaudeAgentOptions(
            mcp_servers={"translation-orchestrator": mcp_server},
            allowed_tools=TOOL_NAMES + ["Task"],
            agents=_get_agents(),
            system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
        )

        prompt = self._build_prompt()

        print(f"Starting translation orchestrator for: {self.book_path}")
        print(f"Target language: {self.language}")
        print(f"Model: {self.model}")
        if self.profile_path:
            print(f"Profile: {self.profile_path}")
        print()

        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)

            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            print(block.text)

    def _build_prompt(self) -> str:
        """Build the orchestration prompt from CLI options."""
        parts = [f"Translate the book at: {self.book_path}"]
        parts.append(f"Target language: {self.language}")

        if self.model != "auto":
            parts.append(f"Use model: {self.model}")
        else:
            parts.append("Choose the best model (sonnet for most, opus for literary fiction)")

        if self.source_lang != "auto":
            parts.append(f"Source language: {self.source_lang}")

        if self.profile_path:
            parts.append(f"Use translation profile: {self.profile_path}")
        else:
            parts.append(f"Check profiles in: {self.profiles_dir}")

        steps = []
        if not self.skip_analysis:
            steps.append("1. Analyze the book (metadata, language, genre, cost estimate)")
        if not self.profile_path:
            steps.append("2. Select or create an appropriate translation profile")
        if not self.skip_test:
            steps.append("3. Run a test translation (5 paragraphs) and verify quality")
        steps.append("4. Run the full translation")
        if not self.skip_quality_check:
            steps.append("5. Quality spot-check (10-20 samples)")
        steps.append("6. Generate a report")

        parts.append(f"\nFollow these steps:\n" + "\n".join(steps))

        if self.resume:
            parts.append("\nResume any interrupted translation (resume=true).")

        report_path = os.path.join(self.report_dir, "translation_report.md")
        parts.append(f"\nSave the final report to: {report_path}")

        return "\n".join(parts)


async def run_orchestrator(**kwargs):
    """Convenience function to create and run the orchestrator."""
    orchestrator = TranslationOrchestrator(**kwargs)
    await orchestrator.run()
