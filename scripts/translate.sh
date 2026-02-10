#!/usr/bin/env bash
set -euo pipefail

# ─── Wrapper script for common translation operations ─────────────────────────
# Usage:
#   ./scripts/translate.sh <book.epub> [options]
#   ./scripts/translate.sh book.epub --profile lovecraft --model opus
#   ./scripts/translate.sh book.epub --language fr --profile scifi
#   ./scripts/translate.sh book.epub --test 5

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PROFILES_DIR="$PROJECT_DIR/examples/profiles"

# ─── Defaults ────────────────────────────────────────────────────────────────
BOOK=""
LANGUAGE="de"
MODEL="3pass-sonnet"
PROFILE=""
TEST_NUM=""
SKIP_REVIEW=""
RESUME=""
EXTRA_ARGS=""

# ─── Parse arguments ────────────────────────────────────────────────────────
usage() {
    cat <<EOF
Usage: $(basename "$0") <book.epub> [options]

Options:
  --language, -l LANG     Target language (default: de)
  --model, -m MODEL       Model: sonnet (default), opus
  --profile, -p NAME      Profile name (without path/extension)
                          Available: $(ls "$PROFILES_DIR"/*.json 2>/dev/null | xargs -I{} basename {} .json | grep -v _template | tr '\n' ', ')
  --test, -t NUM          Test with first NUM paragraphs
  --skip-review           Skip review pass (cheaper, faster)
  --resume                Resume interrupted translation
  --help, -h              Show this help

Examples:
  $(basename "$0") book.epub                                  # EN→DE with Sonnet
  $(basename "$0") book.epub -p lovecraft -m opus             # Lovecraft, Opus
  $(basename "$0") book.epub -l fr -p scifi                   # EN→FR sci-fi
  $(basename "$0") book.epub -t 5                             # Test 5 paragraphs
EOF
    exit 0
}

[ $# -eq 0 ] && usage

BOOK="$1"; shift

while [ $# -gt 0 ]; do
    case "$1" in
        --language|-l) LANGUAGE="$2"; shift 2 ;;
        --model|-m)
            case "$2" in
                opus)   MODEL="3pass-opus" ;;
                sonnet) MODEL="3pass-sonnet" ;;
                *)      MODEL="$2" ;;
            esac; shift 2 ;;
        --profile|-p) PROFILE="$2"; shift 2 ;;
        --test|-t)    TEST_NUM="$2"; shift 2 ;;
        --skip-review) SKIP_REVIEW="--skip-review"; shift ;;
        --resume)     RESUME="--resume"; shift ;;
        --help|-h)    usage ;;
        *)            EXTRA_ARGS="$EXTRA_ARGS $1"; shift ;;
    esac
done

if [ ! -f "$BOOK" ]; then
    echo "Error: Book not found: $BOOK"
    exit 1
fi

# ─── Build command ──────────────────────────────────────────────────────────
CMD="python3 $PROJECT_DIR/make_book.py --book_name $BOOK -m $MODEL"
CMD="$CMD --single_translate --language $LANGUAGE --use_context"

if [ -n "$PROFILE" ]; then
    PROFILE_PATH="$PROFILES_DIR/${PROFILE}.json"
    if [ ! -f "$PROFILE_PATH" ]; then
        echo "Error: Profile not found: $PROFILE_PATH"
        echo "Available profiles:"
        ls "$PROFILES_DIR"/*.json 2>/dev/null | xargs -I{} basename {} .json | grep -v _template | sed 's/^/  /'
        exit 1
    fi
    CMD="$CMD --translation-profile $PROFILE_PATH"
fi

[ -n "$TEST_NUM" ] && CMD="$CMD --test --test_num $TEST_NUM"
[ -n "$SKIP_REVIEW" ] && CMD="$CMD $SKIP_REVIEW"
[ -n "$RESUME" ] && CMD="$CMD $RESUME"
[ -n "$EXTRA_ARGS" ] && CMD="$CMD $EXTRA_ARGS"

echo "═══════════════════════════════════════════════════════"
echo "  Book:     $BOOK"
echo "  Language: $LANGUAGE"
echo "  Model:    $MODEL"
[ -n "$PROFILE" ] && echo "  Profile:  $PROFILE"
[ -n "$TEST_NUM" ] && echo "  Test:     $TEST_NUM paragraphs"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "→ $CMD"
echo ""

exec $CMD
