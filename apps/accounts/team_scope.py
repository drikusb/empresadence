"""A page's team scope: the navbar's active team, or every team the user may see.

The Rocks and Scorecards lists and the dashboard offer the same switch, so
they share the helpers here and behave alike. Each page keeps its choice
under its own session key, so widening one page does not widen another.
"""
from django.db.models import Count

from .scoping import get_active_org, get_assignable_teams

SCOPE_TEAM = 'team'
SCOPE_ALL = 'all'
SCOPES = (SCOPE_TEAM, SCOPE_ALL)


def get_scope(request, session_key, default=SCOPE_TEAM):
    """Return the page scope: ``'team'`` (the navbar's active team) or ``'all'``.

    ``?scope=`` switches it and the choice is kept in the session under
    ``session_key``, so links that carry no scope keep showing the same teams.
    Anything else in ``?scope=`` is ignored in favour of the session, and
    ``default`` applies until the user has chosen. The lists start narrow;
    the dashboard starts wide.
    """
    scope = request.GET.get('scope')
    if scope in SCOPES:
        request.session[session_key] = scope
        return scope
    scope = request.session.get(session_key)
    return scope if scope in SCOPES else default


def get_visible_teams(request):
    """Teams whose records the user may list: their own, or every team for an org admin."""
    return get_assignable_teams(request.user, get_active_org(request))


def count_other_teams(queryset, team, visible_teams):
    """How many records in ``queryset`` each visible team other than ``team`` has.

    Returns ``[(team, n), ...]`` in ``visible_teams`` order, leaving out teams
    with none. The caller narrows ``queryset`` first (quarter, status, active
    flag) so the counts match what the all-teams view would list.
    """
    counts = dict(
        queryset.filter(team__in=visible_teams).exclude(team=team)
        .order_by().values('team').annotate(n=Count('id')).values_list('team', 'n')
    )
    return [(t, counts[t.pk]) for t in visible_teams if t.pk in counts]


def summarise_other_teams(counts):
    """``'Beta: 2, Gamma: 1'`` for the hint link's tooltip."""
    return ', '.join(f'{t.name}: {n}' for t, n in counts)
