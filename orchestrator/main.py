"""CLI entry point for the translation orchestrator."""

import argparse
import asyncio
import sys


def parse_args(argv=None):
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="translation-orchestrator",
        description="Claude Agent SDK translation orchestrator — automates the full "
                    "3-pass literary translation workflow.",
    )

    parser.add_argument(
        "book_path",
        help="Path to the book file (epub, txt, or pdf)",
    )
    parser.add_argument(
        "--language", "-l",
        default="de",
        help="Target language code (default: de)",
    )
    parser.add_argument(
        "--model", "-m",
        default="auto",
        choices=["auto", "3pass-sonnet", "3pass-opus"],
        help="Translation model (default: auto — agent decides)",
    )
    parser.add_argument(
        "--profile", "-p",
        default="",
        dest="profile_path",
        help="Path to existing translation profile (skip profile selection)",
    )
    parser.add_argument(
        "--source-lang",
        default="auto",
        help="Source language code (default: auto-detect)",
    )
    parser.add_argument(
        "--profiles-dir",
        default="examples/profiles",
        help="Directory containing profile JSON files (default: examples/profiles/)",
    )
    parser.add_argument(
        "--report-dir",
        default=".",
        help="Directory for output reports (default: current directory)",
    )
    parser.add_argument(
        "--skip-analysis",
        action="store_true",
        help="Skip book analysis step",
    )
    parser.add_argument(
        "--skip-test",
        action="store_true",
        help="Skip test translation step",
    )
    parser.add_argument(
        "--skip-quality-check",
        action="store_true",
        help="Skip quality review step",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume interrupted translation",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show all agent messages",
    )

    return parser.parse_args(argv)


def main(argv=None):
    """Main entry point."""
    args = parse_args(argv)

    from .orchestrator import run_orchestrator

    asyncio.run(run_orchestrator(
        book_path=args.book_path,
        language=args.language,
        model=args.model,
        profile_path=args.profile_path,
        source_lang=args.source_lang,
        profiles_dir=args.profiles_dir,
        report_dir=args.report_dir,
        skip_analysis=args.skip_analysis,
        skip_test=args.skip_test,
        skip_quality_check=args.skip_quality_check,
        resume=args.resume,
        verbose=args.verbose,
    ))


if __name__ == "__main__":
    main()
