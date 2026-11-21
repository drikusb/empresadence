from django.contrib import admin
from .models import (
    Membership, Organization, OrganizationDomain, OrganizationInvitation, Team, UserProfile,
)


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    raw_id_fields = ['user']


class OrganizationDomainInline(admin.TabularInline):
    model = OrganizationDomain
    extra = 0
    fields = ['hostname', 'is_primary']


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'created_at']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at', 'updated_at']
    inlines = [OrganizationDomainInline, MembershipInline]


@admin.register(OrganizationDomain)
class OrganizationDomainAdmin(admin.ModelAdmin):
    list_display = ['hostname', 'organization', 'is_primary']
    list_filter = ['organization', 'is_primary']
    search_fields = ['hostname', 'organization__name']
    readonly_fields = ['created_at']


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ['name', 'organization', 'member_count', 'created_at']
    list_filter = ['organization']
    search_fields = ['name', 'organization__name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ['user', 'organization', 'role', 'created_at']
    list_filter = ['role', 'organization']
    search_fields = ['user__username', 'user__email', 'organization__name']
    raw_id_fields = ['user']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(OrganizationInvitation)
class OrganizationInvitationAdmin(admin.ModelAdmin):
    list_display = ['user', 'organization', 'role', 'invited_by', 'created_at', 'expires_at', 'accepted_at']
    list_filter = ['organization', 'role']
    search_fields = ['user__username', 'user__email', 'organization__name']
    raw_id_fields = ['user', 'invited_by']
    filter_horizontal = ['teams']
    readonly_fields = ['created_at']


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'created_at']
    search_fields = ['user__username', 'user__email', 'user__first_name', 'user__last_name']
    filter_horizontal = ['teams']
    raw_id_fields = ['user']
    readonly_fields = ['created_at', 'updated_at']
