"""What one organisation calls the standard building blocks of its operating rhythm.

The generic vocabulary (Priorities, Weekly Meeting, ...) is the default. An
organisation stores only the words it changes, so the defaults can evolve in
code without a data migration. Templates read ``terms`` (see the context
processor) or use ``{% term %}``; Python code calls ``get_terms(request)``.
"""
from .scoping import get_active_org

TERMS = [
    ('rock', 'Priority', 'Priorities', 'Quarterly priorities'),
    ('issue', 'Blocker', 'Blockers', ''),
    ('todo', 'Action', 'Actions', ''),
    ('scorecard', 'Metrics Board', 'Metrics Boards', ''),
    ('meeting', 'Weekly Meeting', 'Weekly Meetings', 'The weekly leadership meeting'),
    ('vto', 'Vision Plan', 'Vision Plans', 'The organisation\'s long-term vision and plan'),
    ('accountability_chart', 'Org Chart', 'Org Charts', ''),
    ('seat', 'Role', 'Roles', ''),
    ('core_value', 'Value', 'Values', ''),
    ('milestone', 'Step', 'Steps', ''),
    ('headline', 'Update', 'Updates', ''),
    ('segue', 'Check-in', 'Check-ins', ''),
    ('ids', 'PRS', 'PRS', 'Problem, Solve, Resolve'),
    ('cascading_message', 'Key Message', 'Key Messages', ''),
]

TERM_KEYS = [key for key, *_ in TERMS]


def plural_key(key):
    """The attribute and storage key for a term's plural: ``rocks``, but ``ids_plural``."""
    return f'{key}_plural' if key.endswith('s') else f'{key}s'


PLURAL_KEYS = {key: plural_key(key) for key in TERM_KEYS}

DEFAULTS = {}
for _key, _singular, _plural, _ in TERMS:
    DEFAULTS[_key] = _singular
    DEFAULTS[PLURAL_KEYS[_key]] = _plural
del _key, _singular, _plural


class Terms:
    """The effective vocabulary: defaults with an organisation's overrides applied.

    ``terms.rock`` / ``terms.rocks`` give the singular and plural directly;
    ``terms.get('rock', count=n)`` picks one by count.
    """

    def __init__(self, overrides=None):
        self._values = dict(DEFAULTS)
        for key, value in (overrides or {}).items():
            if key in DEFAULTS and isinstance(value, str) and value.strip():
                self._values[key] = value.strip()

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        try:
            return self._values[name]
        except KeyError:
            raise AttributeError(name) from None

    def __contains__(self, key):
        return key in self._values

    def __eq__(self, other):
        return isinstance(other, Terms) and other._values == self._values

    def __repr__(self):
        return f'Terms({self.overrides()!r})'

    def get(self, key, count=None, plural=False, lower=False):
        if key not in PLURAL_KEYS:
            raise KeyError(key)
        if count is not None:
            plural = count != 1
        value = self._values[PLURAL_KEYS[key] if plural else key]
        return value.lower() if lower else value

    def as_dict(self):
        return dict(self._values)

    def overrides(self):
        return {key: value for key, value in self._values.items() if value != DEFAULTS[key]}


def terms_for(org):
    return Terms(org.terminology if org is not None else None)


def get_terms(request):
    """Terms for the request's organisation, memoised because every template asks."""
    if not hasattr(request, '_terms'):
        request._terms = terms_for(_org_for(request))
    return request._terms


def _org_for(request):
    user = getattr(request, 'user', None)
    if user is not None and user.is_authenticated:
        org = get_active_org(request)
        if org is not None:
            return org
    return getattr(request, 'host_org', None)
