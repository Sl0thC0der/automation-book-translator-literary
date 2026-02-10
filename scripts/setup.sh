#!/usr/bin/env bash
set -euo pipefail

# ─── Setup script for automation-book-translator-literary ─────────────────────
# Installs dependencies, validates environment, and runs a smoke test.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "═══════════════════════════════════════════════════════"
echo "  automation-book-translator-literary — Setup"
echo "═══════════════════════════════════════════════════════"
echo ""

# ─── Check Python ────────────────────────────────────────────────────────────
echo "→ Checking Python..."
if ! command -v python3 &>/dev/null; then
    echo "✗ python3 not found. Install Python 3.10+."
    exit 1
fi
PYVER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "  Python $PYVER"

# ─── Install dependencies ───────────────────────────────────────────────────
echo ""
echo "→ Installing Python dependencies..."
cd "$PROJECT_DIR"
pip install -r requirements.txt --quiet
pip install pymupdf --quiet
echo "  Done."

# ─── Check API key ──────────────────────────────────────────────────────────
echo ""
echo "→ Checking API key..."
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
    echo "  ANTHROPIC_API_KEY is set."
elif [ -n "${BBM_CLAUDE_API_KEY:-}" ]; then
    echo "  BBM_CLAUDE_API_KEY is set."
else
    echo "  ⚠ No API key found. Set one of:"
    echo "    export ANTHROPIC_API_KEY=sk-ant-XXXXX"
    echo "    export BBM_CLAUDE_API_KEY=sk-ant-XXXXX"
fi

# ─── Validate profiles ─────────────────────────────────────────────────────
echo ""
echo "→ Validating translation profiles..."
PROFILE_COUNT=0
for f in "$PROJECT_DIR"/examples/profiles/*.json; do
    [ "$(basename "$f")" = "_template.json" ] && continue
    python3 -c "import json; json.load(open('$f'))" 2>/dev/null && PROFILE_COUNT=$((PROFILE_COUNT + 1)) || echo "  ✗ Invalid JSON: $f"
done
echo "  $PROFILE_COUNT profiles OK."

# ─── Smoke test ─────────────────────────────────────────────────────────────
echo ""
echo "→ Running import smoke test..."
cd "$PROJECT_DIR"
python3 -c "
from book_maker.translator import MODEL_DICT
from book_maker.translator.claude_3pass_translator import Claude3Pass
assert '3pass' in MODEL_DICT
assert '3pass-opus' in MODEL_DICT
assert '3pass-sonnet' in MODEL_DICT
print('  Translator imports: OK')
print(f'  Models available: {len(MODEL_DICT)}')
"

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  Setup complete!"
echo ""
echo "  Quick start:"
echo "    python make_book.py --book_name book.epub -m 3pass-sonnet \\"
echo "      --single_translate --language de --use_context \\"
echo "      --test --test_num 5"
echo "═══════════════════════════════════════════════════════"
