"""
Django admin configuration for the Analyzer app.
"""
from django.contrib import admin

from .models import AnalysisJob, FileSummary, ModuleSummary, Project, ProjectOutput


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    """Admin view for Project model."""

    list_display = ('name', 'upload_type', 'total_files', 'created_at')
    list_filter = ('upload_type', 'created_at')
    search_fields = ('name',)
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(AnalysisJob)
class AnalysisJobAdmin(admin.ModelAdmin):
    """Admin view for AnalysisJob model."""

    list_display = ('project', 'status', 'progress_percent', 'created_at', 'completed_at')
    list_filter = ('status',)
    search_fields = ('project__name',)
    readonly_fields = ('id', 'created_at')


@admin.register(FileSummary)
class FileSummaryAdmin(admin.ModelAdmin):
    """Admin view for FileSummary model."""

    list_display = ('file_path', 'language', 'project', 'file_size', 'created_at')
    list_filter = ('language',)
    search_fields = ('file_path', 'project__name')
    readonly_fields = ('id', 'created_at')


@admin.register(ModuleSummary)
class ModuleSummaryAdmin(admin.ModelAdmin):
    """Admin view for ModuleSummary model."""

    list_display = ('module_path', 'project', 'file_count', 'created_at')
    search_fields = ('module_path', 'project__name')
    readonly_fields = ('id', 'created_at')


@admin.register(ProjectOutput)
class ProjectOutputAdmin(admin.ModelAdmin):
    """Admin view for ProjectOutput model."""

    list_display = ('output_type', 'project', 'created_at', 'updated_at')
    list_filter = ('output_type',)
    search_fields = ('project__name',)
    readonly_fields = ('id', 'created_at', 'updated_at')
