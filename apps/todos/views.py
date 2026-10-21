from datetime import date

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, View
from django.shortcuts import redirect
from django.urls import reverse_lazy, reverse
from django.contrib import messages

from .models import ToDo
from .forms import ToDoForm
from apps.accounts.scoping import OrgScopedMixin, get_active_team, get_org_object_or_404
from apps.accounts.terminology import get_terms


# ---------------------------------------------------------------------------
# List — My To-Dos / Team To-Dos
# ---------------------------------------------------------------------------

class ToDoListView(LoginRequiredMixin, ListView):
    model = ToDo
    template_name = 'todos/todo_list.html'
    context_object_name = 'todos'

    def get_queryset(self):
        team = get_active_team(self.request)
        if not team:
            return ToDo.objects.none()

        view = self.request.GET.get('view', 'mine')
        status = self.request.GET.get('status', 'open')

        qs = (
            ToDo.objects
            .filter(team=team)
            .select_related('owner', 'owner__profile', 'team', 'linked_rock', 'linked_issue')
        )

        if view == 'mine':
            qs = qs.filter(owner=self.request.user)

        if status == 'complete':
            qs = qs.filter(status=ToDo.STATUS_COMPLETE).order_by('-completed_at')
        elif status == 'overdue':
            qs = qs.filter(status=ToDo.STATUS_OPEN, due_date__lt=date.today())
        else:
            qs = qs.filter(status=ToDo.STATUS_OPEN).order_by('due_date')

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = date.today()
        ctx.update({
            'view_filter': self.request.GET.get('view', 'mine'),
            'status_filter': self.request.GET.get('status', 'open'),
            'today': today,
        })
        try:
            ctx['overdue_count'] = (
                ToDo.objects
                .filter(owner=self.request.user, status=ToDo.STATUS_OPEN, due_date__lt=today)
                .count()
            )
        except Exception:
            ctx['overdue_count'] = 0
        return ctx


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

class ToDoCreateView(LoginRequiredMixin, CreateView):
    model = ToDo
    form_class = ToDoForm
    template_name = 'todos/todo_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['team'] = get_active_team(self.request)
        kwargs['user'] = self.request.user
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        # Pre-fill owner with current user
        initial['owner'] = self.request.user
        # Pre-fill linked_rock or linked_issue from GET params
        rock_pk = self.request.GET.get('rock')
        issue_pk = self.request.GET.get('issue')
        if rock_pk:
            initial['linked_rock'] = rock_pk
        if issue_pk:
            initial['linked_issue'] = issue_pk
        return initial

    def form_valid(self, form):
        terms = get_terms(self.request)
        messages.success(self.request, f'{terms.todo} "{form.instance.title}" created.')
        return super().form_valid(form)

    def get_success_url(self):
        next_url = self.request.GET.get('next') or self.request.POST.get('next')
        return next_url or reverse('todos:list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['action'] = 'Create'
        return ctx


class ToDoUpdateView(LoginRequiredMixin, OrgScopedMixin, UpdateView):
    model = ToDo
    form_class = ToDoForm
    template_name = 'todos/todo_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['team'] = self.get_object().team
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        terms = get_terms(self.request)
        messages.success(self.request, f'{terms.todo} "{form.instance.title}" updated.')
        return super().form_valid(form)

    def get_success_url(self):
        next_url = self.request.GET.get('next') or self.request.POST.get('next')
        return next_url or reverse('todos:list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['action'] = 'Edit'
        return ctx


class ToDoDeleteView(LoginRequiredMixin, OrgScopedMixin, DeleteView):
    model = ToDo
    template_name = 'todos/todo_confirm_delete.html'
    success_url = reverse_lazy('todos:list')

    def form_valid(self, form):
        terms = get_terms(self.request)
        messages.success(self.request, f'{terms.todo} "{self.object.title}" deleted.')
        return super().form_valid(form)


# ---------------------------------------------------------------------------
# Complete toggle
# ---------------------------------------------------------------------------

class ToDoCompleteView(LoginRequiredMixin, View):
    """POST-only: toggle a To-Do between open and complete."""

    def post(self, request, pk):
        todo = get_org_object_or_404(request, ToDo, pk=pk)
        if todo.is_complete:
            todo.mark_open()
        else:
            todo.mark_complete()
        next_url = request.POST.get('next') or reverse('todos:list')
        return redirect(next_url)


# ---------------------------------------------------------------------------
# Escalate to Issue
# ---------------------------------------------------------------------------

class ToDoEscalateView(LoginRequiredMixin, View):
    """POST-only: create an Issue from an overdue To-Do and link them."""

    def post(self, request, pk):
        todo = get_org_object_or_404(request, ToDo, pk=pk)
        from apps.issues.models import Issue, IssueActivity

        issue = Issue.objects.create(
            title=f'Escalated: {todo.title}',
            description=(
                f'Escalated from an overdue To-Do (open {todo.days_open} days).\n\n'
                f'Original task: {todo.description or todo.title}'
            ),
            originating_team=todo.team,
            created_by=request.user,
            issue_type=Issue.TYPE_SHORT_TERM,
            status=Issue.STATUS_OPEN,
        )
        IssueActivity.objects.create(
            issue=issue,
            actor=request.user,
            action=IssueActivity.ACTION_CREATED,
            notes=f'Created by escalating overdue To-Do "{todo.title}".',
        )
        # Link the todo to the new issue
        todo.linked_issue = issue
        todo.save(update_fields=['linked_issue', 'updated_at'])

        terms = get_terms(request)
        messages.success(request, f'{terms.issue} created from "{todo.title}".')
        return redirect('issues:detail', pk=issue.pk)
