"""
Database models for the CodeMap Analyzer.

Stores project metadata, analysis jobs, file/module summaries,
and final generated outputs (documentation, diagrams, etc.).
"""
import uuid

from django.db import models


from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Project(models.Model):
    """
    Represents an uploaded project (ZIP file or Git repository).

    Stores metadata about the project source, its name, and
    the local path where the extracted/cloned files are stored.
    """

    UPLOAD_TYPE_CHOICES = [
        ('zip', 'ZIP Upload'),
        ('git', 'Git Repository'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='projects')
    name = models.CharField(max_length=255, help_text="Project name (derived from filename or repo)")
    upload_type = models.CharField(max_length=10, choices=UPLOAD_TYPE_CHOICES)
    source_file = models.FileField(upload_to='projects/uploads/', blank=True, null=True)
    source_url = models.URLField(max_length=500, blank=True, null=True)
    extracted_path = models.CharField(
        max_length=1000, blank=True, null=True,
        help_text="Local filesystem path to the extracted/cloned project"
    )
    total_files = models.IntegerField(default=0, help_text="Number of relevant files found")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Project'
        verbose_name_plural = 'Projects'

    def __str__(self):
        return f"{self.name} ({self.get_upload_type_display()})"


class AnalysisJob(models.Model):
    """
    Tracks the status of a background analysis job for a project.

    Linked to a Celery task via `celery_task_id`. The status progresses
    through: pending → processing → completed (or failed).
    """

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.OneToOneField(
        Project, on_delete=models.CASCADE, related_name='analysis_job'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    celery_task_id = models.CharField(max_length=255, blank=True, null=True)
    progress_message = models.CharField(
        max_length=500, blank=True, default='',
        help_text="Human-readable progress description"
    )
    progress_percent = models.IntegerField(
        default=0, help_text="Estimated completion percentage (0-100)"
    )
    error_message = models.TextField(blank=True, default='')
    started_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Analysis Job'
        verbose_name_plural = 'Analysis Jobs'

    def __str__(self):
        return f"Job for {self.project.name} — {self.get_status_display()}"


class FileSummary(models.Model):
    """
    Stores the AI-generated summary for a single source file.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='file_summaries'
    )
    file_path = models.CharField(max_length=1000, help_text="Relative path within the project")
    language = models.CharField(max_length=50, blank=True, default='')
    file_size = models.IntegerField(default=0, help_text="File size in bytes")
    summary = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['file_path']
        verbose_name = 'File Summary'
        verbose_name_plural = 'File Summaries'

    def __str__(self):
        return f"{self.file_path} — {self.project.name}"


class ModuleSummary(models.Model):
    """
    Stores the AI-generated summary for a module (directory/folder).

    Aggregates the individual file summaries within that module.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='module_summaries'
    )
    module_path = models.CharField(max_length=1000, help_text="Relative directory path")
    summary = models.TextField(blank=True, default='')
    file_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['module_path']
        verbose_name = 'Module Summary'
        verbose_name_plural = 'Module Summaries'

    def __str__(self):
        return f"{self.module_path} — {self.project.name}"


class ProjectOutput(models.Model):
    """
    Stores a final generated output document for a project.

    Each output_type corresponds to one deliverable:
    overview, architecture, workflow, usecase_diagram, user_manual.
    """

    OUTPUT_TYPE_CHOICES = [
        ('overview', 'Project Overview'),
        ('architecture', 'Architecture Explanation'),
        ('workflow', 'Workflow Explanation'),
        ('usecase_diagram', 'Use Case Diagram (Mermaid)'),
        ('user_manual', 'User Manual'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='outputs'
    )
    output_type = models.CharField(max_length=30, choices=OUTPUT_TYPE_CHOICES)
    content = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['output_type']
        unique_together = [('project', 'output_type')]
        verbose_name = 'Project Output'
        verbose_name_plural = 'Project Outputs'

    def __str__(self):
        return f"{self.get_output_type_display()} — {self.project.name}"


# ── Add Email OTP Model ──────────────────────────────
class EmailOTP(models.Model):
    email = models.EmailField()
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    failed_attempts = models.IntegerField(default=0)

    def is_valid(self):
        # OTP is valid for 5 minutes
        expiration_time = self.created_at + timezone.timedelta(minutes=5)
        return timezone.now() <= expiration_time

    def __str__(self):
        return f"{self.email} - {self.otp}"
