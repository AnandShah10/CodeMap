"""
Celery background tasks for the CodeMap Analyzer.

Orchestrates the full analysis pipeline using multi-agent parallel processing:
1. Extract/clone the project
2. Traverse and filter relevant files
3. Generate file-level AI summaries (parallel)
4. Generate module-level AI summaries (parallel)
5. Generate project-level outputs (parallel where possible)
"""
import logging
import os
import uuid
from collections import defaultdict
from pathlib import Path

from celery import shared_task
from django.conf import settings
from django.utils import timezone
from django.core.mail import send_mail
from django.urls import reverse
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger('analyzer')

# Default number of parallel AI workers
DEFAULT_AGENT_WORKERS = 3


@shared_task(bind=True, max_retries=1, time_limit=3600, soft_time_limit=3300)
def analyze_project(self, job_id: str) -> dict:
    """
    Main background task that processes an uploaded project end-to-end.
    Uses multi-agent orchestrator for parallel AI processing.

    Args:
        job_id: UUID of the AnalysisJob to process.

    Returns:
        Dict with status and summary of the analysis.
    """
    from analyzer.models import AnalysisJob, FileSummary, ModuleSummary, ProjectOutput, Project
    from analyzer.services.ai_service import AIService
    from analyzer.services.multi_agent import MultiAgentOrchestrator
    from analyzer.services.file_processor import (
        clone_repo,
        extract_zip,
        get_relevant_files,
        read_file_content,
    )

    try:
        job = AnalysisJob.objects.select_related('project').get(id=job_id)
    except AnalysisJob.DoesNotExist:
        logger.error(f"AnalysisJob {job_id} not found")
        return {'status': 'error', 'message': 'Job not found'}

    project = job.project

    # Determine selected components (empty list = all)
    selected_components = project.selected_components
    if not selected_components:
        selected_components = Project.ALL_COMPONENTS

    try:
        # ── Initialize multi-agent orchestrator ──────────────
        ai = AIService()
        num_workers = DEFAULT_AGENT_WORKERS
        orchestrator = MultiAgentOrchestrator(ai, max_workers=num_workers)

        # ── Update status to processing ──────────────────────
        job.status = 'processing'
        job.started_at = timezone.now()
        job.progress_message = f'Starting analysis with {num_workers} parallel agents...'
        job.progress_percent = 5
        job.agent_workers = num_workers
        job.save(update_fields=['status', 'started_at', 'progress_message', 'progress_percent', 'agent_workers'])

        # ── Step 1: Extract / Clone ──────────────────────────
        _update_progress(job, 'Preparing project files...', 10)

        project_dir = os.path.join(
            settings.MEDIA_ROOT, 'projects', 'extracted', str(project.id)
        )

        extracted_path = project.extracted_path
        if not extracted_path or not os.path.exists(extracted_path):
            if project.upload_type == 'zip' and project.source_file:
                zip_path = project.source_file.path
                extracted_path = extract_zip(zip_path, project_dir)
            elif project.upload_type == 'git' and project.source_url:
                extracted_path = clone_repo(project.source_url, project_dir)
            else:
                raise ValueError("Invalid project configuration: no source file or URL")

            project.extracted_path = extracted_path
            project.save(update_fields=['extracted_path'])

        # ── Step 2: Traverse and filter files ────────────────
        _update_progress(job, 'Scanning project files...', 15)

        max_file_size_kb = settings.MAX_SINGLE_FILE_SIZE_KB
        relevant_files = get_relevant_files(extracted_path, max_file_size_kb)

        if not relevant_files:
            raise ValueError("No relevant source files found in the project")

        project.total_files = len(relevant_files)
        project.save(update_fields=['total_files'])

        logger.info(f"Found {len(relevant_files)} files for project {project.name}")

        # ── Step 3: File-level summaries (PARALLEL) ──────────
        _update_progress(job, f'Analyzing {len(relevant_files)} files with {num_workers} agents...', 20)

        # Pre-load existing file summaries for resume support
        existing_file_summaries = {
            fs.file_path: fs for fs in FileSummary.objects.filter(project=project)
        }

        # Separate files into already-processed and new
        files_to_process = []
        file_summaries_data = []

        for file_info in relevant_files:
            if file_info['path'] in existing_file_summaries:
                fs = existing_file_summaries[file_info['path']]
                file_summaries_data.append({
                    'file_path': fs.file_path,
                    'summary': fs.summary,
                    'language': fs.language,
                })
            else:
                files_to_process.append(file_info)

        if files_to_process:
            # Check cancellation before starting expensive work
            job.refresh_from_db(fields=['status'])
            if job.status == 'cancelled':
                logger.info(f"Analysis cancelled for project {project.name}")
                return {'status': 'cancelled', 'message': 'Job was cancelled by the user'}

            # Process new files in parallel
            new_summaries = orchestrator.process_files_parallel(
                job, files_to_process, read_file_content
            )

            # Save to DB and collect
            for fs_data in new_summaries:
                FileSummary.objects.create(
                    project=project,
                    file_path=fs_data['file_path'],
                    language=fs_data['language'],
                    file_size=fs_data.get('size', 0),
                    summary=fs_data['summary'],
                )
                file_summaries_data.append(fs_data)

        # Check cancellation
        job.refresh_from_db(fields=['status'])
        if job.status == 'cancelled':
            return {'status': 'cancelled', 'message': 'Job was cancelled by the user'}

        # ── Step 4: Module-level summaries (PARALLEL) ────────
        _update_progress(job, 'Generating module summaries...', 65)

        modules = defaultdict(list)
        for fs in file_summaries_data:
            module_path = str(Path(fs['file_path']).parent)
            if module_path == '.':
                module_path = '(root)'
            modules[module_path].append(fs)

        # Pre-load existing module summaries for resume
        existing_module_summaries = {
            ms.module_path: ms for ms in ModuleSummary.objects.filter(project=project)
        }

        modules_to_process = {}
        module_summaries_data = []

        for module_path, module_files in modules.items():
            if module_path in existing_module_summaries:
                ms = existing_module_summaries[module_path]
                module_summaries_data.append({
                    'module_path': ms.module_path,
                    'summary': ms.summary,
                    'file_count': ms.file_count,
                })
            else:
                modules_to_process[module_path] = module_files

        if modules_to_process:
            job.refresh_from_db(fields=['status'])
            if job.status == 'cancelled':
                return {'status': 'cancelled', 'message': 'Job was cancelled by the user'}

            new_module_summaries = orchestrator.process_modules_parallel(job, modules_to_process)

            for ms_data in new_module_summaries:
                ModuleSummary.objects.create(
                    project=project,
                    module_path=ms_data['module_path'],
                    summary=ms_data['summary'],
                    file_count=ms_data['file_count'],
                )
                module_summaries_data.append(ms_data)

        # Combine module summaries for project-level prompts
        combined_module_summaries = '\n\n'.join(
            f"### `{ms['module_path']}` ({ms['file_count']} files)\n{ms['summary']}"
            for ms in module_summaries_data
        )

        # ── Step 5: Project-level outputs (PARALLEL) ─────────
        existing_outputs = {
            po.output_type: po.content for po in ProjectOutput.objects.filter(project=project)
        }

        file_list = "\n".join([fs['file_path'] for fs in file_summaries_data])

        job.refresh_from_db(fields=['status'])
        if job.status == 'cancelled':
            return {'status': 'cancelled', 'message': 'Job was cancelled by the user'}

        generated_outputs = orchestrator.generate_outputs_parallel(
            job=job,
            project=project,
            combined_summaries=combined_module_summaries,
            file_list=file_list,
            selected_components=selected_components,
            existing_outputs=existing_outputs,
        )

        # Save any newly generated outputs
        for output_type, content in generated_outputs.items():
            if output_type not in existing_outputs:
                ProjectOutput.objects.update_or_create(
                    project=project,
                    output_type=output_type,
                    defaults={'content': content}
                )

        # ── Complete ─────────────────────────────────────────
        job.status = 'completed'
        job.progress_message = 'Analysis complete!'
        job.progress_percent = 100
        job.completed_at = timezone.now()
        job.save(update_fields=[
            'status', 'progress_message', 'progress_percent', 'completed_at'
        ])

        _send_completion_notification(job)

        logger.info(f"Analysis completed for project: {project.name} ({num_workers} agents)")
        return {
            'status': 'completed',
            'project_id': str(project.id),
            'total_files': len(file_summaries_data),
            'total_modules': len(module_summaries_data),
            'agent_workers': num_workers,
        }

    except Exception as e:
        logger.exception(f"Analysis failed for project {project.name}: {e}")
        job.status = 'failed'
        job.error_message = str(e)[:2000]
        job.progress_message = f'Analysis failed: {str(e)[:200]}'
        job.completed_at = timezone.now()
        job.save(update_fields=[
            'status', 'error_message', 'progress_message', 'completed_at'
        ])
        
        _send_completion_notification(job)
        return {'status': 'failed', 'error': str(e)[:500]}


def _update_progress(job, message: str, percent: int) -> None:
    """
    Update the job's progress message and percentage.
    """
    job.progress_message = message
    job.progress_percent = percent
    job.save(update_fields=['progress_message', 'progress_percent'])
    logger.info(f"[{percent}%] {message}")


def _send_completion_notification(job):
    """Send an email notification to the user when analysis is done."""
    project = job.project
    user = project.user
    
    if not user or not user.email:
        logger.info(f"No email found for user of project {project.name}. Skipping notification.")
        return

    subject = f"CodeMap Analysis Complete: {project.name}"
    if job.status == 'failed':
        subject = f"CodeMap Analysis Failed: {project.name}"
    
    site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
    results_url = f"{site_url}{reverse('analyzer:project_results', kwargs={'project_id': project.id})}"
    subject = f"CodeMap Analysis: {project.name} - {job.status.title()}"
    
    site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
    results_url = f"{site_url}/projects/{project.id}/results/"
    if job.status != 'completed':
        results_url = f"{site_url}/projects/{project.id}/status/"

    context = {
        'project': project,
        'job': job,
        'results_url': results_url,
        'current_year': timezone.now().year,
    }

    html_message = render_to_string('analyzer/emails/analysis_completion.html', context)
    plain_message = strip_tags(html_message)
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'CodeMap <noreply@codemap.ai>')
    
    try:
        send_mail(
            subject,
            plain_message,
            from_email,
            [user.email],
            html_message=html_message,
            fail_silently=True
        )
        logger.info(f"Notification email sent to {user.email} for project {project.id}")
    except Exception as e:
        logger.error(f"Failed to send notification email: {str(e)}")
