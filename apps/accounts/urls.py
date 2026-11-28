from django.urls import include, path
from . import views
from .views_export import OrganizationExportView

app_name = 'accounts'

urlpatterns = [
    path('org/setup/', views.OrgSetupView.as_view(), name='org_setup'),
    path('org/', views.OrgDetailView.as_view(), name='org_detail'),
    path('org/settings/', views.OrgSettingsView.as_view(), name='org_settings'),
    path('org/settings/terminology/', views.OrgTerminologyView.as_view(), name='org_terminology'),
    path('org/<int:pk>/switch/', views.OrgSwitchView.as_view(), name='org_switch'),
    path('org/export/', OrganizationExportView.as_view(), name='org_export'),
    path('teams/', views.TeamListView.as_view(), name='team_list'),
    path('teams/new/', views.TeamCreateView.as_view(), name='team_create'),
    path('teams/<int:pk>/', views.TeamDetailView.as_view(), name='team_detail'),
    path('teams/<int:pk>/edit/', views.TeamUpdateView.as_view(), name='team_update'),
    path('teams/<int:pk>/members/', views.TeamMembersUpdateView.as_view(), name='team_members'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('accounts/2fa/', include('apps.accounts.two_factor.urls')),
    path('profile/edit/', views.ProfileEditView.as_view(), name='profile_edit'),
    path('media/avatars/<path:name>', views.MediaAvatarView.as_view(), name='media_avatar'),
    path('users/', views.UserListView.as_view(), name='user_list'),
    path('users/invite/', views.UserInviteView.as_view(), name='user_invite'),
    path('users/invitations/<int:pk>/resend/', views.InvitationResendView.as_view(), name='invitation_resend'),
    path('users/invitations/<int:pk>/withdraw/', views.InvitationWithdrawView.as_view(), name='invitation_withdraw'),
    # Under /accounts/ so the invited person, who is not a member yet, can open
    # it on an organisation's own hostname (see OPEN_PATH_PREFIXES).
    path(
        'accounts/invitations/<int:pk>/<str:token>/',
        views.InvitationRespondView.as_view(), name='invitation_respond',
    ),
    path('teams/<int:pk>/switch/', views.TeamSwitchView.as_view(), name='team_switch'),
    path('search/', views.SearchView.as_view(), name='search'),
]
