"""A standing guard against EOS Worldwide's trademarked wording creeping back in.

Each entry in ``TRADEMARKED_TERMS`` is a mark as it might appear written out
for a person to read — not as a Python identifier. The ``vto`` app label, the
``VTO``/``VTOSection`` model and class names, and the ``apps.vision`` package
are kept on purpose (see ``apps/vision/apps.py``) and are not what this
guards against; renaming them would need a database migration for every
self-hosted install, for no user-visible benefit. So this only reads:

* every template, where any occurrence of a mark reaches either the browser
  or, for a ``{# #}``/``{% comment %}`` block, the page source a maintainer
  reads;
* the ``apps/`` Python source, but only the ``help_text=``, ``verbose_name=``
  and ``label=`` keyword values, and the display half of a Django choices
  tuple (``(SOME_CONSTANT, '...')``) — the shapes the earlier sweeps actually
  found a mark hiding in. A bare identifier or a docstring mentioning the
  historical EOS vocabulary for a reader's own orientation is not shown to
  anyone running the app, so it is out of scope on purpose.

Migrations and the tests directory itself are skipped: migrations are frozen
history (changing one means writing a fresh migration, not editing the old
one), and this file's own strings would otherwise match themselves.

"Level 10 Meeting" is deliberately left off ``TRADEMARKED_TERMS`` until #121
removes the remaining instances — adding it here first would fail CI on code
this guard isn't meant to touch.
"""
import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

TRADEMARKED_TERMS = [
    'V/TO', 'VTO', 'IDS', 'Core Focus', '10-Year Target', '3-Year Picture',
    'Accountability Chart',
]

SYMBOL_PATTERN = re.compile('[®™]')

ASSIGNMENT_PATTERN = re.compile(
    r"(?:help_text|verbose_name(?:_plural)?|label)\s*=\s*f?(['\"])((?:(?!\1).)*)\1"
)
CHOICES_TUPLE_PATTERN = re.compile(
    r"\(\s*[A-Z_][A-Z0-9_]*\s*,\s*f?(['\"])((?:(?!\1).)*)\1\s*\)"
)

ROOT = Path(settings.BASE_DIR)
THIS_FILE = Path(__file__).resolve()


def _term_pattern(term):
    return re.compile(r'\b' + re.escape(term) + r'\b')


def _source_files(base, suffix):
    for path in sorted(base.rglob(f'*{suffix}')):
        if path.resolve() == THIS_FILE:
            continue
        if 'migrations' in path.parts or 'tests' in path.parts:
            continue
        yield path


class NoTrademarkedWordingTest(SimpleTestCase):
    """What the earlier sweeps removed must not come back."""

    def test_no_registered_or_trademark_symbols(self):
        offenders = [
            str(path.relative_to(ROOT))
            for base, suffix in ((ROOT / 'apps', '.py'), (ROOT / 'templates', '.html'))
            for path in _source_files(base, suffix)
            if SYMBOL_PATTERN.search(path.read_text(encoding='utf-8'))
        ]
        self.assertEqual(offenders, [], f'\N{REGISTERED SIGN} or \N{TRADE MARK SIGN} found in: {offenders}')

    def test_no_trademarked_terms_in_templates(self):
        offenders = [
            (str(path.relative_to(ROOT)), term)
            for path in _source_files(ROOT / 'templates', '.html')
            for term in TRADEMARKED_TERMS
            if _term_pattern(term).search(path.read_text(encoding='utf-8'))
        ]
        self.assertEqual(offenders, [], f'Trademarked wording found: {offenders}')

    def test_no_trademarked_terms_in_python_display_text(self):
        offenders = []
        for path in _source_files(ROOT / 'apps', '.py'):
            text = path.read_text(encoding='utf-8')
            values = [m.group(2) for m in ASSIGNMENT_PATTERN.finditer(text)]
            values += [m.group(2) for m in CHOICES_TUPLE_PATTERN.finditer(text)]
            for value in values:
                for term in TRADEMARKED_TERMS:
                    if _term_pattern(term).search(value):
                        offenders.append((str(path.relative_to(ROOT)), term, value))
        self.assertEqual(offenders, [], f'Trademarked wording found: {offenders}')
