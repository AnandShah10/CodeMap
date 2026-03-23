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

        for i, file_info in enumerate(relevant_files, 1):
            # Update progress (20% → 60% for file summaries)
            file_progress = 20 + int((i / total_files) * 40)
            if i % 5 == 0 or i == total_files:
                _update_progress(
                    job,
                    f'Analyzing file {i}/{total_files}: {file_info["path"]}',
                    min(file_progress, 60),
                )

            content = read_file_content(file_info['abs_path'])
            if not content or len(content.strip()) == 0:
                continue

            try:
                summary = ai.summarize_file(
                    file_path=file_info['path'],
                    content=content,
                    language=file_info['language'],
                )
            except Exception as e:
                logger.warning(f"Failed to summarize {file_info['path']}: {e}")
                summary = f"[Analysis failed: {str(e)[:100]}]"

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

        for i, (module_path, module_files) in enumerate(modules.items(), 1):
            module_progress = 65 + int((i / total_modules) * 10)
            _update_progress(
                job,
                f'Analyzing module {i}/{total_modules}: {module_path}',
                min(module_progress, 75),
            )

            try:
                mod_summary = ai.summarize_module(module_path, module_files)
            except Exception as e:
                logger.warning(f"Failed to summarize module {module_path}: {e}")
                mod_summary = f"[Module analysis failed: {str(e)[:100]}]"

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

        # 5a. Project Overview
        _update_progress(job, 'Generating project overview...', 78)
        overview = ai.generate_project_overview(project.name, combined_module_summaries)
        ProjectOutput.objects.create(
            project=project, output_type='overview', content=overview
        )

        # 5b. Architecture
        _update_progress(job, 'Generating architecture explanation...', 83)
        architecture = ai.generate_architecture(project.name, combined_module_summaries)
        ProjectOutput.objects.create(
            project=project, output_type='architecture', content=architecture
        )

        # 5c. Workflow
        _update_progress(job, 'Generating workflow explanation...', 88)
        workflow = ai.generate_workflow(project.name, combined_module_summaries)
        ProjectOutput.objects.create(
            project=project, output_type='workflow', content=workflow
        )

        # 5d. Use Case Diagram (Mermaid)
        _update_progress(job, 'Generating use case diagram...', 92)
        usecase_diagram = ai.generate_usecase_diagram(project.name, overview)
        ProjectOutput.objects.create(
            project=project, output_type='usecase_diagram', content=usecase_diagram
        )

        # 5e. User Manual
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
