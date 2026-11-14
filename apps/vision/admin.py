from django.contrib import admin
from .models import (
    VTO, VTOCoreValue, VTOSection, VTOSectionHistory,
    VisionPage, VisionSectionDefinition, VisionSectionGroup,
)


class VTOCoreValueInline(admin.TabularInline):
    model = VTOCoreValue
    extra = 1


class VTOSectionInline(admin.TabularInline):
    model = VTOSection
    extra = 0
    readonly_fields = ('last_edited_by', 'last_edited_at')


@admin.register(VTO)
class VTOAdmin(admin.ModelAdmin):
    list_display = ('organization', 'created_at', 'updated_at')
    inlines = [VTOCoreValueInline, VTOSectionInline]


@admin.register(VTOCoreValue)
class VTOCoreValueAdmin(admin.ModelAdmin):
    list_display = ('name', 'vto', 'order')
    search_fields = ('name',)


@admin.register(VTOSection)
class VTOSectionAdmin(admin.ModelAdmin):
    list_display = ('vto', 'key', 'last_edited_by', 'last_edited_at')
    list_filter = ('key',)
    readonly_fields = ('last_edited_by', 'last_edited_at')


# ── Per-organisation document structure ──────────────────────────────────────
#
# An organisation with no VisionPage rows uses the shipped default structure;
# adding pages here is what opts it into its own. See apps/vision/structure.py.

class VisionSectionDefinitionInline(admin.TabularInline):
    model = VisionSectionDefinition
    extra = 1
    fields = ('order', 'key', 'label', 'render_as', 'half_width')


class VisionSectionGroupInline(admin.TabularInline):
    model = VisionSectionGroup
    extra = 1
    fields = ('order', 'label', 'hint')
    show_change_link = True


@admin.register(VisionPage)
class VisionPageAdmin(admin.ModelAdmin):
    list_display = ('label', 'organization', 'order')
    list_filter = ('organization',)
    inlines = [VisionSectionGroupInline]


@admin.register(VisionSectionGroup)
class VisionSectionGroupAdmin(admin.ModelAdmin):
    list_display = ('label', 'page', 'order')
    list_filter = ('page__organization',)
    inlines = [VisionSectionDefinitionInline]


@admin.register(VisionSectionDefinition)
class VisionSectionDefinitionAdmin(admin.ModelAdmin):
    list_display = ('key', 'label', 'group', 'render_as', 'order')
    list_filter = ('group__page__organization', 'render_as')
    search_fields = ('key', 'label')
