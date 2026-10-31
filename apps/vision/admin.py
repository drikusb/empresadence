from django.contrib import admin
from .models import VTO, VTOCoreValue, VTOSection, VTOSectionHistory


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
