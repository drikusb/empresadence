import csv
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from itertools import groupby

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.shortcuts import redirect
from django.urls import reverse_lazy, reverse
from django.utils.text import slugify
from django.contrib import messages

from .models import Scorecard, ScorecardMetric, ScorecardEntry, _current_week_start, _current_month_start
from .forms import ScorecardForm, ScorecardMetricForm
from apps.accounts.scoping import (
    OrgScopedMixin, get_active_org, get_active_team, get_org_object_or_404,
)
from apps.accounts.team_scope import (
    SCOPE_ALL, count_other_teams, get_scope, get_visible_teams, summarise_other_teams,
)
from apps.accounts.terminology import get_terms

SCOPE_SESSION_KEY = 'scorecards_scope'


def _build_periods(n=13, frequency='weekly'):
    """Return list of n period-start dates ending with the current period, oldest first."""
    if frequency == 'weekly':
        latest = _current_week_start()
        return [latest - timedelta(weeks=i) for i in range(n - 1, -1, -1)]
    latest = _current_month_start()
    periods = []
    y, m = latest.year, latest.month
    for _ in range(n):
        periods.append(date(y, m, 1))
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return list(reversed(periods))


def _build_scorecard_table(scorecard):
    """Build the 13-week periods and per-metric cell table for a scorecard's history.

    Returns (periods, table) where periods is oldest→newest period-start dates and
    table is [{'metric': m, 'cells': [entry|None, ...]}] aligned to those periods.
    Shared by the detail view and the CSV export so both render the same data.
    """
    metrics = list(scorecard.active_metrics.select_related('owner', 'owner__profile'))
    periods = _build_periods(13, 'weekly')

    entry_map = {
        (e.metric_id, e.period_start): e
        for e in ScorecardEntry.objects.filter(
            metric__scorecard=scorecard,
            period_start__gte=periods[0],
            period_start__lte=periods[-1],
        ).select_related('entered_by')
    }

    table = [
        {'metric': m, 'cells': [entry_map.get((m.pk, p)) for p in periods]}
        for m in metrics
    ]
    return periods, table


# ---------------------------------------------------------------------------
# Scorecard CRUD
# ---------------------------------------------------------------------------

class ScorecardListView(LoginRequiredMixin, ListView):
    """The active team's Scorecards, or every visible team's with ``?scope=all``.

    The scope works as on the Rocks list (see ``apps.accounts.team_scope``) and
    is kept in the session under its own key, so the two lists are switched
    independently. The default is the active team, as before.
    """
    model = Scorecard
    template_name = 'scorecards/scorecard_list.html'
    context_object_name = 'scorecards'

    def get_queryset(self):
        if get_scope(self.request, SCOPE_SESSION_KEY) == SCOPE_ALL:
            team_filter = {'team__in': get_visible_teams(self.request)}
        else:
            team = get_active_team(self.request)
            if not team:
                return Scorecard.objects.none()
            team_filter = {'team': team}
        return (
            Scorecard.objects
            .filter(is_active=True, **team_filter)
            .select_related('team')
            .prefetch_related('metrics')
            .order_by('team__name', 'name')
        )

    def _scope_context(self):
        """Which teams the list covers, and how many Scorecards the others have."""
        scope = get_scope(self.request, SCOPE_SESSION_KEY)
        active_team = get_active_team(self.request)
        visible_teams = list(get_visible_teams(self.request))
        other_team_counts = []
        if scope == SCOPE_ALL:
            scoped_teams = visible_teams
        else:
            scoped_teams = [active_team] if active_team else []
            if active_team:
                other_team_counts = count_other_teams(
                    Scorecard.objects.filter(is_active=True), active_team, visible_teams
                )
        return {
            'scope': scope,
            'active_team': active_team,
            'visible_teams': visible_teams,
            'scoped_teams': scoped_teams,
            'other_team_counts': other_team_counts,
            'other_scorecards_total': sum(n for _, n in other_team_counts),
            'other_teams_summary': summarise_other_teams(other_team_counts),
        }

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        current_week = _current_week_start()

        # For each scorecard, attach a quick summary for the current week
        summaries = []
        for sc in ctx['scorecards']:
            metrics = list(sc.active_metrics)
            entries = {
                e.metric_id: e
                for e in ScorecardEntry.objects.filter(
                    metric__scorecard=sc,
                    period_start=current_week,
                )
            }
            on_track = sum(1 for m in metrics if entries.get(m.pk) and entries[m.pk].on_track)
            off_track = sum(1 for m in metrics if entries.get(m.pk) and not entries[m.pk].on_track)
            missing = sum(1 for m in metrics if m.pk not in entries)
            summaries.append({
                'scorecard': sc,
                'metrics': metrics,
                'entries': entries,
                'on_track': on_track,
                'off_track': off_track,
                'missing': missing,
                'total': len(metrics),
            })
        ctx['summaries'] = summaries
        # One group per team, in team-name order, for the all-teams view's headings.
        ctx['teams_summaries'] = [
            (team, list(team_summaries))
            for team, team_summaries in groupby(summaries, key=lambda s: s['scorecard'].team)
        ]
        ctx['current_week'] = current_week
        ctx.update(self._scope_context())
        return ctx


class ScorecardCreateView(LoginRequiredMixin, CreateView):
    model = Scorecard
    form_class = ScorecardForm
    template_name = 'scorecards/scorecard_form.html'

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw['organization'] = get_active_org(self.request)
        return kw

    def form_valid(self, form):
        terms = get_terms(self.request)
        messages.success(self.request, f'{terms.scorecard} "{form.instance.name}" created.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['action'] = 'Create'
        return ctx


class ScorecardUpdateView(LoginRequiredMixin, OrgScopedMixin, UpdateView):
    model = Scorecard
    form_class = ScorecardForm
    template_name = 'scorecards/scorecard_form.html'

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw['organization'] = self.object.team.organization
        return kw

    def form_valid(self, form):
        terms = get_terms(self.request)
        messages.success(self.request, f'{terms.scorecard} "{form.instance.name}" updated.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['action'] = 'Edit'
        return ctx


class ScorecardDeleteView(LoginRequiredMixin, OrgScopedMixin, DeleteView):
    model = Scorecard
    template_name = 'scorecards/scorecard_confirm_delete.html'
    success_url = reverse_lazy('scorecards:list')

    def form_valid(self, form):
        terms = get_terms(self.request)
        messages.success(self.request, f'{terms.scorecard} "{self.object.name}" deleted.')
        return super().form_valid(form)


# ---------------------------------------------------------------------------
# Scorecard detail — 13-week table
# ---------------------------------------------------------------------------

class ScorecardDetailView(LoginRequiredMixin, OrgScopedMixin, DetailView):
    model = Scorecard
    template_name = 'scorecards/scorecard_detail.html'
    context_object_name = 'scorecard'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        sc = self.object
        periods, table = _build_scorecard_table(sc)

        ctx['periods'] = periods
        ctx['table'] = table
        ctx['current_week'] = _current_week_start()
        ctx['metric_form'] = ScorecardMetricForm(organization=sc.team.organization)
        return ctx


class ScorecardCsvExportView(LoginRequiredMixin, View):
    """Export a scorecard's 13-week history as CSV."""

    def get(self, request, pk):
        scorecard = get_org_object_or_404(request, Scorecard, pk=pk)
        periods, table = _build_scorecard_table(scorecard)

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = (
            f'attachment; filename="{slugify(scorecard.name)}-scorecard.csv"'
        )

        writer = csv.writer(response)
        writer.writerow(['Metric', 'Owner', 'Goal'] + [p.isoformat() for p in periods])
        for row in table:
            metric = row['metric']
            owner_name = metric.owner.get_full_name() or metric.owner.username
            cells = [
                metric.format_value(entry.value) if entry else ''
                for entry in row['cells']
            ]
            writer.writerow([metric.name, owner_name, metric.format_goal()] + cells)
        return response


# ---------------------------------------------------------------------------
# Metric CRUD
# ---------------------------------------------------------------------------

class MetricCreateView(LoginRequiredMixin, CreateView):
    model = ScorecardMetric
    form_class = ScorecardMetricForm
    template_name = 'scorecards/metric_form.html'

    def get_scorecard(self):
        return get_org_object_or_404(self.request, Scorecard, pk=self.kwargs['scorecard_pk'])

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw['organization'] = self.get_scorecard().team.organization
        return kw

    def form_valid(self, form):
        form.instance.scorecard = self.get_scorecard()
        messages.success(self.request, f'Metric "{form.instance.name}" added.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('scorecards:detail', kwargs={'pk': self.kwargs['scorecard_pk']})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['scorecard'] = self.get_scorecard()
        ctx['action'] = 'Add'
        return ctx


class MetricUpdateView(LoginRequiredMixin, OrgScopedMixin, UpdateView):
    model = ScorecardMetric
    org_lookup = 'scorecard__team__organization'
    form_class = ScorecardMetricForm
    template_name = 'scorecards/metric_form.html'

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw['organization'] = self.object.scorecard.team.organization
        return kw

    def form_valid(self, form):
        messages.success(self.request, f'Metric "{form.instance.name}" updated.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('scorecards:detail', kwargs={'pk': self.object.scorecard_id})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['scorecard'] = self.object.scorecard
        ctx['action'] = 'Edit'
        return ctx


class MetricDeleteView(LoginRequiredMixin, View):
    """Soft-delete a metric (sets is_active=False)."""

    def post(self, request, pk):
        metric = get_org_object_or_404(
            request, ScorecardMetric, org_lookup='scorecard__team__organization', pk=pk
        )
        scorecard_pk = metric.scorecard_id
        metric.is_active = False
        metric.save(update_fields=['is_active'])
        messages.success(request, f'Metric "{metric.name}" removed.')
        return redirect('scorecards:detail', pk=scorecard_pk)


# ---------------------------------------------------------------------------
# Weekly entry — POST multiple values in one form
# ---------------------------------------------------------------------------

class ScorecardEntryView(LoginRequiredMixin, View):
    """GET: show entry form for current period. POST: save/update entries."""

    template_name = 'scorecards/entry_form.html'

    def _get_data(self, scorecard):
        metrics = list(scorecard.active_metrics.select_related('owner'))
        current_week = _current_week_start()
        existing = {
            e.metric_id: e
            for e in ScorecardEntry.objects.filter(
                metric__scorecard=scorecard,
                period_start=current_week,
            )
        }
        return metrics, current_week, existing

    def get(self, request, pk):
        scorecard = get_org_object_or_404(request, Scorecard, pk=pk)
        metrics, current_week, existing = self._get_data(scorecard)
        return self._render(request, scorecard, metrics, current_week, existing, errors={})

    def post(self, request, pk):
        scorecard = get_org_object_or_404(request, Scorecard, pk=pk)
        metrics, current_week, existing = self._get_data(scorecard)
        errors = {}
        saved = 0

        for metric in metrics:
            raw = request.POST.get(f'value_{metric.pk}', '').strip()
            notes = request.POST.get(f'notes_{metric.pk}', '').strip()
            if not raw:
                continue  # skip blanks — don't delete existing
            try:
                value = Decimal(raw)
            except InvalidOperation:
                errors[metric.pk] = 'Invalid number.'
                continue

            entry = existing.get(metric.pk)
            if entry:
                entry.value = value
                entry.notes = notes
                entry.entered_by = request.user
                entry.save()
            else:
                ScorecardEntry.objects.create(
                    metric=metric,
                    period_start=current_week,
                    value=value,
                    notes=notes,
                    entered_by=request.user,
                )
            saved += 1

        if errors:
            return self._render(request, scorecard, metrics, current_week, existing, errors=errors)

        messages.success(request, f'{saved} metric{"s" if saved != 1 else ""} updated for week of {current_week}.')
        return redirect('scorecards:detail', pk=pk)

    def _render(self, request, scorecard, metrics, current_week, existing, errors):
        from django.shortcuts import render
        rows = []
        for m in metrics:
            entry = existing.get(m.pk)
            rows.append({
                'metric': m,
                'entry': entry,
                'error': errors.get(m.pk),
                'value_str': str(entry.value) if entry else '',
            })
        return render(request, self.template_name, {
            'scorecard': scorecard,
            'rows': rows,
            'current_week': current_week,
            'period_label': f'Week of {current_week.strftime("%b %d, %Y")}',
        })


# ---------------------------------------------------------------------------
# Escalate off-track metric to Issue
# ---------------------------------------------------------------------------

class MetricEscalateView(LoginRequiredMixin, View):
    """POST-only: create an Issue from an off-track metric entry."""

    def post(self, request, pk):
        entry = get_org_object_or_404(
            request, ScorecardEntry,
            org_lookup='metric__scorecard__team__organization', pk=pk,
        )
        metric = entry.metric

        from apps.issues.models import Issue, IssueActivity
        issue = Issue.objects.create(
            title=f'Off-track: {metric.name}',
            description=(
                f'Metric "{metric.name}" on {metric.scorecard.name} was off-track '
                f'for the week of {entry.period_start}.\n\n'
                f'Value: {metric.format_value(entry.value)} '
                f'(goal: {metric.format_goal()})\n'
                f'{("Notes: " + entry.notes) if entry.notes else ""}'
            ),
            originating_team=metric.scorecard.team,
            created_by=request.user,
            issue_type=Issue.TYPE_SHORT_TERM,
            status=Issue.STATUS_OPEN,
        )
        IssueActivity.objects.create(
            issue=issue,
            actor=request.user,
            action=IssueActivity.ACTION_CREATED,
            notes=f'Created from off-track Scorecard metric "{metric.name}".',
        )
        terms = get_terms(request)
        messages.success(request, f'{terms.issue} created for off-track metric "{metric.name}".')
        return redirect('issues:detail', pk=issue.pk)
