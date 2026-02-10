#!/usr/bin/env bash
set -euo pipefail

# ─── Integration test: translates 3 paragraphs and validates output ──────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "═══════════════════════════════════════════════════════"
echo "  Translation Pipeline — Integration Test"
echo "═══════════════════════════════════════════════════════"
echo ""

cd "$PROJECT_DIR"

python3 -c "
from book_maker.translator import MODEL_DICT
from book_maker.translator.claude_3pass_translator import Claude3Pass, PARA_DELIMITER
import glob, json, atexit

atexit._clear()
failures = []

def check(name, cond):
    if not cond: failures.append(name)
    return cond

# 1. Model registration
for m in ['3pass','3pass-opus','3pass-sonnet']:
    check(f'model_{m}', m in MODEL_DICT and MODEL_DICT[m] == Claude3Pass)
print('✓ Models registered')

# 2. Constructor
t = Claude3Pass(key='test', language='German', api_base=None,
    context_flag=True, context_paragraph_limit=5, temperature=1.0, source_lang='en')
check('compat', hasattr(t,'context_list'))
check('source', t.source_language == 'English')
check('cache', hasattr(t,'total_cache_read_tokens'))
print('✓ Constructor')

# 3. All profiles load
for pf in sorted(glob.glob('examples/profiles/*.json')):
    if '_template' in pf: continue
    tx = Claude3Pass(key='test', language='German', context_flag=True,
        context_paragraph_limit=5, temperature=1.0, source_lang='en')
    tx.load_profile(pf)
    d = json.load(open(pf))
    check(f'profile_{pf}', tx.profile_name == d['name'])
print('✓ Profiles valid')

# 4. Lovecraft profile
t.load_profile('examples/profiles/lovecraft.json')
check('lc_nouns', len(t.protected_nouns) == 62)
check('lc_glossary', len(t.glossary) == 10)
print(f'✓ Lovecraft profile ({len(t.protected_nouns)} nouns, {len(t.glossary)} glossary)')

# 5. Mock dispatch
def mock_api(system, user, temp, max_tokens=8192, retries=5, use_cache=True):
    t.total_requests += 1; t.total_input_tokens += 100; t.total_output_tokens += 50
    if PARA_DELIMITER in user:
        parts = user.split(PARA_DELIMITER)
        return PARA_DELIMITER.join([f'T{i}' for i in range(len(parts))])
    if 'EDITOR REVIEW' in user: return 'QUALITY_OK'
    if 'ORIGINAL' in user and 'TRANSLATION' in user: return 'QUALITY_OK'
    return 'Translated'
t._api_call = mock_api

t.translate('Short.')
t.translate('x ' * 200)
r3 = t.translate('A.\nB.\nC.')
check('batch', len(r3.split(chr(10))) == 3)
check('dispatch', t.pass1_only_count == 1 and t.full_3pass_count == 2)
print(f'✓ Dispatch (p1={t.pass1_only_count}, 3p={t.full_3pass_count})')

# 6. Loader wiring
from ebooklib import epub
from book_maker.loader.epub_loader import EPUBBookLoader
book = epub.EpubBook()
book.set_identifier('t1'); book.set_title('T'); book.set_language('en')
ch = epub.EpubHtml(title='C', file_name='c.xhtml', lang='en')
ch.content = b'<html><body><p>Test.</p></body></html>'
book.add_item(ch); book.spine = ['nav', ch]
book.add_item(epub.EpubNcx()); book.add_item(epub.EpubNav())
epub.write_epub('/tmp/t.epub', book)
ldr = EPUBBookLoader('/tmp/t.epub', Claude3Pass, 'key', False,
    language='German', model_api_base=None, is_test=True, test_num=3,
    prompt_config=None, single_translate=True, context_flag=True,
    context_paragraph_limit=5, temperature=1.0, source_lang='en', parallel_workers=1)
check('loader', ldr.translate_model.__class__ == Claude3Pass)
import os; os.remove('/tmp/t.epub')
print('✓ EPUBBookLoader wiring')

# Report
if failures:
    print(f'\n✗ {len(failures)} FAILED: {failures}')
    exit(1)
else:
    print(f'\n═══════════════════════════════════════════════════════')
    print(f'  ALL TESTS PASSED ✓')
    print(f'═══════════════════════════════════════════════════════')
"
