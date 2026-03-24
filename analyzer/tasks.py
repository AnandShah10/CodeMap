"""
Celery background tasks for the CodeMap Analyzer.

Orchestrates the full analysis pipeline:
1. Extract/clone the project
2. Traverse and filter relevant files
3. Generate file-level AI summaries
4. Generate module-level AI summaries
5. Generate project-level outputs (overview, architecture,
   workflow, use case diagram, user manual)
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


@shared_task(bind=True, max_retries=1, time_limit=3600, soft_time_limit=3300)
def analyze_project(self, job_id: str) -> dict:
    """
    Main background task that processes an uploaded project end-to-end.

    Args:
        job_id: UUID of the AnalysisJob to process.

    Returns:
        Dict with status and summary of the analysis.
    """
    # Import here to avoid circular imports
    from analyzer.models import AnalysisJob, FileSummary, ModuleSummary, ProjectOutput
    from analyzer.services.ai_service import AIService
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

    try:
        # ── Update status to processing ──────────────────────
        job.status = 'processing'
        job.started_at = timezone.now()
        job.progress_message = 'Starting analysis...'
        job.progress_percent = 5
        job.save(update_fields=['status', 'started_at', 'progress_message', 'progress_percent'])

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

        # ── Step 3: File-level summaries ─────────────────────
        _update_progress(job, f'Analyzing {len(relevant_files)} files...', 20)

        ai = AIService()
        file_summaries_data = []
        total_files = len(relevant_files)

        # Pre-load existing file summaries to allow for resumes
        existing_file_summaries = {
            fs.file_path: fs for fs in FileSummary.objects.filter(project=project)
        }

        for i, file_info in enumerate(relevant_files, 1):
            # Update progress (20% → 60% for file summaries)
            file_progress = 20 + int((i / total_files) * 40)
            if i % 5 == 0 or i == total_files:
                _update_progress(
                    job,
                    f'Analyzing file {i}/{total_files}: {file_info["path"]}',
                    min(file_progress, 60),
                )

            # Check if this file was already processed previously
            if file_info['path'] in existing_file_summaries:
                fs = existing_file_summaries[file_info['path']]
                file_summaries_data.append({
                    'file_path': fs.file_path,
                    'summary': fs.summary,
                    'language': fs.language,
                })
                continue

            content = read_file_content(file_info['abs_path'])
            if not content or len(content.strip()) == 0:
                continue

            # Poll for cancellation
            job.refresh_from_db(fields=['status'])
            if job.status == 'cancelled':
                logger.info(f"Analysis cancelled for project {project.name}")
                return {'status': 'cancelled', 'message': 'Job was cancelled by the user'}

            try:
                summary = ai.summarize_file(
                    file_path=file_info['path'],
                    content=content,
                    language=file_info['language'],
                )
            except Exception as e:
                logger.warning(f"Failed to summarize {file_info['path']}: {e}")
                err_str = str(e)
                summary = f"[Analysis failed: {err_str[:100]}]"

            FileSummary.objects.create(
                project=project,
                file_path=file_info['path'],
                language=file_info['language'],
                file_size=file_info['size'],
                summary=summary,
            )

            file_summaries_data.append({
                'file_path': file_info['path'],
                'summary': summary,
                'language': file_info['language'],
            })

        # ── Step 4: Module-level summaries ───────────────────
        _update_progress(job, 'Generating module summaries...', 65)

        # Group files by directory
        modules = defaultdict(list)
        for fs in file_summaries_data:
            module_path = str(Path(fs['file_path']).parent)
            if module_path == '.':
                module_path = '(root)'
            modules[module_path].append(fs)

        module_summaries_data = []
        total_modules = len(modules)

        existing_module_summaries = {
            ms.module_path: ms for ms in ModuleSummary.objects.filter(project=project)
        }

        for i, (module_path, module_files) in enumerate(modules.items(), 1):
            module_progress = 65 + int((i / total_modules) * 10)
            _update_progress(
                job,
                f'Analyzing module {i}/{total_modules}: {module_path}',
                min(module_progress, 75),
            )

            # Check if already processed
            if module_path in existing_module_summaries:
                ms = existing_module_summaries[module_path]
                module_summaries_data.append({
                    'module_path': ms.module_path,
                    'summary': ms.summary,
                    'file_count': ms.file_count,
                })
                continue

            # Poll for cancellation
            job.refresh_from_db(fields=['status'])
            if job.status == 'cancelled':
                logger.info(f"Analysis cancelled for project {project.name}")
                return {'status': 'cancelled', 'message': 'Job was cancelled by the user'}

            try:
                mod_summary = ai.summarize_module(module_path, module_files)
            except Exception as e:
                logger.warning(f"Failed to summarize module {module_path}: {e}")
                err_str = str(e)
                mod_summary = f"[Module analysis failed: {err_str[:100]}]"

            ModuleSummary.objects.create(
                project=project,
                module_path=module_path,
                summary=mod_summary,
                file_count=len(module_files),
            )

            module_summaries_data.append({
                'module_path': module_path,
                'summary': mod_summary,
                'file_count': len(module_files),
            })

        # Combine module summaries for project-level prompts
        combined_module_summaries = '\n\n'.join(
            f"### `{ms['module_path']}` ({ms['file_count']} files)\n{ms['summary']}"
            for ms in module_summaries_data
        )

        # ── Step 5: Project-level outputs ────────────────────
        existing_outputs = {
            po.output_type: po.content for po in ProjectOutput.objects.filter(project=project)
        }

        # 5a. Project Overview
        if 'overview' in existing_outputs:
            overview = existing_outputs['overview']
        else:
            _update_progress(job, 'Generating project overview...', 78)
            overview = ai.generate_project_overview(project.name, combined_module_summaries)
            ProjectOutput.objects.create(
                project=project, output_type='overview', content=overview
            )

        # 5b. Architecture
        if 'architecture' not in existing_outputs:
            _update_progress(job, 'Generating architecture explanation...', 83)
            architecture = ai.generate_architecture(project.name, combined_module_summaries)
            ProjectOutput.objects.create(
                project=project, output_type='architecture', content=architecture
            )
        else:
            architecture = existing_outputs['architecture']

        # 5c. Workflow
        if 'workflow' not in existing_outputs:
            _update_progress(job, 'Generating workflow explanation...', 88)
            workflow = ai.generate_workflow(project.name, combined_module_summaries)
            ProjectOutput.objects.create(
                project=project, output_type='workflow', content=workflow
            )
        else:
            workflow = existing_outputs['workflow']

        # 5d. Diagrams (UML & Non-UML)
        diagram_types = [
            'class_diagram', 'object_diagram', 'component_diagram', 'composite_structure_diagram',
            'package_diagram', 'deployment_diagram', 'profile_diagram', 'usecase_diagram',
            'activity_diagram', 'state_diagram', 'sequence_diagram', 'communication_diagram',
            'interaction_overview_diagram', 'timing_diagram', 'er_diagram', 'c4_context_diagram',
            'workflow_flowchart', 'mindmap', 'project_structure'
        ]
        
        # Prepare file list for diagram context
        file_list = "\n".join([fs['file_path'] for fs in file_summaries_data])
        
        for i, dtype in enumerate(diagram_types):
            if dtype not in existing_outputs:
                progress = 90 + int((i / len(diagram_types)) * 8)
                display_name = dtype.replace('_', ' ').title()
                _update_progress(job, f'Generating {display_name}...', progress)
                
                # Context for diagram: Use overview, architecture, and file list
                diagram_context = (
                    f"Overview:\n{overview}\n\n"
                    f"Architecture:\n{architecture}\n\n"
                    f"Files:\n{file_list}"
                )
                
                try:
                    diagram_code = ai.generate_diagram(dtype, project.name, diagram_context)
                    ProjectOutput.objects.create(
                        project=project, output_type=dtype, content=diagram_code
                    )
                except Exception as e:
                    logger.error(f"Failed to generate diagram {dtype}: {e}")

        # 5e. User Manual
        if 'user_manual' not in existing_outputs:
            _update_progress(job, 'Generating user manual...', 95)
            user_manual = ai.generate_user_manual(
                project.name, overview, architecture, workflow
            )
            ProjectOutput.objects.create(
                project=project, output_type='user_manual', content=user_manual
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

        logger.info(f"Analysis completed for project: {project.name}")
        return {
            'status': 'completed',
            'project_id': str(project.id),
            'total_files': len(file_summaries_data),
            'total_modules': len(module_summaries_data),
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

    Args:
        job: AnalysisJob instance.
        message: Human-readable progress description.
        percent: Estimated completion percentage (0-100).
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
    
    # Generate the link to view results
    # Note: In a production environment, use a real domain instead of localhost
    site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
    results_url = f"{site_url}{reverse('analyzer:project_results', kwargs={'project_id': project.id})}"
    subject = f"CodeMap Analysis: {project.name} - {job.status.title()}"
    
    # Build absolute results URL
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
