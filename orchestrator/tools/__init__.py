"""MCP tools for the translation orchestrator.

Tools are plain Python functions that can be called directly or wrapped
in the Claude Agent SDK's MCP server for use by agents.
"""

from .analyze import analyze_book
from .profiles import list_profiles, create_profile
from .translate import run_translation
from .quality import extract_paragraphs, quality_spot_check
from .report import generate_report


def create_mcp_server():
    """Create a Claude Agent SDK MCP server with all orchestrator tools.

    Returns:
        An MCP server object suitable for ClaudeAgentOptions.mcp_servers.
    """
    from claude_agent_sdk import tool, create_sdk_mcp_server

    @tool(
        "analyze_book",
        "Extract metadata, detect language, and sample text from a book file (epub/txt/pdf).",
        {"book_path": str, "sample_count": int},
    )
    async def analyze_book_tool(args):
        result = analyze_book(
            book_path=args["book_path"],
            sample_count=args.get("sample_count", 5),
        )
        return {"content": [{"type": "text", "text": result}]}

    @tool(
        "list_profiles",
        "List available translation profiles with their key settings.",
        {"profiles_dir": str},
    )
    async def list_profiles_tool(args):
        result = list_profiles(profiles_dir=args.get("profiles_dir", "examples/profiles"))
        return {"content": [{"type": "text", "text": result}]}

    @tool(
        "create_profile",
        "Create a new translation profile JSON file.",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Profile name"},
                "output_path": {"type": "string", "description": "Where to save the profile"},
                "description": {"type": "string"},
                "source_language": {"type": "string"},
                "style_instructions": {"type": "string"},
                "protected_nouns": {"type": "string", "description": "Comma-separated list"},
                "glossary_seed": {"type": "string", "description": "JSON string of seed glossary"},
                "temp_translate": {"type": "number"},
                "temp_review": {"type": "number"},
                "temp_refine": {"type": "number"},
                "min_review_chars": {"type": "integer"},
                "context_update_interval": {"type": "integer"},
                "glossary_update_interval": {"type": "integer"},
            },
            "required": ["name", "output_path"],
        },
    )
    async def create_profile_tool(args):
        result = create_profile(
            name=args["name"],
            output_path=args["output_path"],
            description=args.get("description", ""),
            source_language=args.get("source_language", "English"),
            style_instructions=args.get("style_instructions", ""),
            protected_nouns=args.get("protected_nouns", ""),
            glossary_seed=args.get("glossary_seed", ""),
            temp_translate=args.get("temp_translate", 0.3),
            temp_review=args.get("temp_review", 0.4),
            temp_refine=args.get("temp_refine", 0.2),
            min_review_chars=args.get("min_review_chars", 300),
            context_update_interval=args.get("context_update_interval", 15),
            glossary_update_interval=args.get("glossary_update_interval", 20),
        )
        return {"content": [{"type": "text", "text": result}]}

    @tool(
        "run_translation",
        "Run 3-pass literary translation on a book. Calls the translator directly as Python library.",
        {
            "type": "object",
            "properties": {
                "book_path": {"type": "string", "description": "Path to book file"},
                "language": {"type": "string", "description": "Target language code (default: de)"},
                "model": {"type": "string", "description": "3pass-sonnet or 3pass-opus"},
                "profile_path": {"type": "string", "description": "Path to profile JSON"},
                "use_context": {"type": "boolean"},
                "skip_review": {"type": "boolean"},
                "test_mode": {"type": "boolean"},
                "test_num": {"type": "integer"},
                "block_size": {"type": "integer"},
                "resume": {"type": "boolean"},
                "source_lang": {"type": "string"},
            },
            "required": ["book_path"],
        },
    )
    async def run_translation_tool(args):
        result = run_translation(
            book_path=args["book_path"],
            language=args.get("language", "de"),
            model=args.get("model", "3pass-sonnet"),
            profile_path=args.get("profile_path", ""),
            use_context=args.get("use_context", True),
            skip_review=args.get("skip_review", False),
            test_mode=args.get("test_mode", False),
            test_num=args.get("test_num", 5),
            block_size=args.get("block_size", 1500),
            resume=args.get("resume", False),
            source_lang=args.get("source_lang", "auto"),
        )
        return {"content": [{"type": "text", "text": result}]}

    @tool(
        "extract_paragraphs",
        "Extract original+translated paragraph pairs from two epub files for quality review.",
        {
            "type": "object",
            "properties": {
                "original_path": {"type": "string"},
                "translated_path": {"type": "string"},
                "sample_count": {"type": "integer"},
                "strategy": {"type": "string", "enum": ["evenly_spaced", "random", "first"]},
            },
            "required": ["original_path", "translated_path"],
        },
    )
    async def extract_paragraphs_tool(args):
        result = extract_paragraphs(
            original_path=args["original_path"],
            translated_path=args["translated_path"],
            sample_count=args.get("sample_count", 10),
            strategy=args.get("strategy", "evenly_spaced"),
        )
        return {"content": [{"type": "text", "text": result}]}

    @tool(
        "quality_spot_check",
        "Evaluate translation quality of a paragraph pair using Claude.",
        {
            "type": "object",
            "properties": {
                "original_text": {"type": "string"},
                "translated_text": {"type": "string"},
                "source_language": {"type": "string"},
                "target_language": {"type": "string"},
                "style_instructions": {"type": "string"},
                "protected_nouns": {"type": "string"},
            },
            "required": ["original_text", "translated_text"],
        },
    )
    async def quality_spot_check_tool(args):
        result = quality_spot_check(
            original_text=args["original_text"],
            translated_text=args["translated_text"],
            source_language=args.get("source_language", "English"),
            target_language=args.get("target_language", "German"),
            style_instructions=args.get("style_instructions", ""),
            protected_nouns=args.get("protected_nouns", ""),
        )
        return {"content": [{"type": "text", "text": result}]}

    @tool(
        "generate_report",
        "Generate a markdown translation quality/cost report.",
        {
            "type": "object",
            "properties": {
                "translation_stats": {"type": "string", "description": "JSON string with TranslationStats"},
                "quality_results": {"type": "string", "description": "JSON string with quality results"},
                "book_metadata": {"type": "string", "description": "JSON string with book metadata"},
                "profile_name": {"type": "string"},
                "model_used": {"type": "string"},
                "output_path": {"type": "string"},
            },
        },
    )
    async def generate_report_tool(args):
        result = generate_report(
            translation_stats=args.get("translation_stats", "{}"),
            quality_results=args.get("quality_results", "{}"),
            book_metadata=args.get("book_metadata", "{}"),
            profile_name=args.get("profile_name", "Default"),
            model_used=args.get("model_used", "claude-sonnet-4-20250514"),
            output_path=args.get("output_path", ""),
        )
        return {"content": [{"type": "text", "text": result}]}

    server = create_sdk_mcp_server(
        name="translation-orchestrator",
        version="0.1.0",
        tools=[
            analyze_book_tool,
            list_profiles_tool,
            create_profile_tool,
            run_translation_tool,
            extract_paragraphs_tool,
            quality_spot_check_tool,
            generate_report_tool,
        ],
    )

    return server


# Tool name constants for use in allowed_tools lists
TOOL_NAMES = [
    "mcp__translation-orchestrator__analyze_book",
    "mcp__translation-orchestrator__list_profiles",
    "mcp__translation-orchestrator__create_profile",
    "mcp__translation-orchestrator__run_translation",
    "mcp__translation-orchestrator__extract_paragraphs",
    "mcp__translation-orchestrator__quality_spot_check",
    "mcp__translation-orchestrator__generate_report",
]
