"""
Views for the CodeMap Analyzer.

Provides both HTML template views and JSON API endpoints
for uploading projects, checking status, and viewing results.
"""
import json
import logging

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm

from .forms import ProjectUploadForm
from .models import AnalysisJob, FileSummary, ModuleSummary, Project, ProjectOutput
from .tasks import analyze_project
from .services.task_queue import background_queue

from django.conf import settings

logger = logging.getLogger('analyzer')


# ──────────────────────────────────────────────
# Template-Based Views
# ──────────────────────────────────────────────
def landing(request):
    """Render the landing page."""
    if request.user.is_authenticated:
        return redirect('analyzer:project_list')
    return render(request, 'analyzer/landing.html')


@login_required
def upload_project(request):
    """
    Handle project upload via web form.

    GET: Display the upload form.
    POST: Process the upload, create a project and job, start analysis.
    """
    if request.method == 'POST':
        form = ProjectUploadForm(request.POST, request.FILES)
        if form.is_valid():
            upload_type = form.cleaned_data['upload_type']
            project_name = form.cleaned_data['project_name']

            # Create the project
            project = Project.objects.create(
                name=project_name,
                upload_type=upload_type,
                user=request.user
            )

            if upload_type == 'zip':
                project.source_file = form.cleaned_data['zip_file']
                project.save(update_fields=['source_file'])
            elif upload_type == 'git':
                project.source_url = form.cleaned_data['git_url']
                project.save(update_fields=['source_url'])

            # Create the analysis job
            job = AnalysisJob.objects.create(
                project=project,
                status='pending',
                progress_message='Job created, waiting to start...',
            )

            # Dispatch the Celery task or Fallback local task
            if settings.USE_CELERY:
                task = analyze_project.delay(str(job.id))
                job.celery_task_id = task.id
            else:
                background_queue.enqueue(analyze_project, str(job.id))
                job.celery_task_id = "local-queue"
                
            job.save(update_fields=['celery_task_id'])

            logger.info(f"Created analysis job {job.id} for project {project.name}")

            return redirect('analyzer:project_status', project_id=project.id)
    else:
        form = ProjectUploadForm()

    return render(request, 'analyzer/upload.html', {'form': form})


@require_GET
def project_status(request, project_id):
    """
    Display the current analysis status for a project.

    Auto-refreshes via JavaScript polling.
    """
    project = get_object_or_404(Project, id=project_id)
    job = get_object_or_404(AnalysisJob, project=project)

    return render(request, 'analyzer/status.html', {
        'project': project,
        'job': job,
    })


@require_GET
def project_results(request, project_id):
    """
    Display the analysis results (documentation, diagrams) for a project.
    """
    project = get_object_or_404(Project, id=project_id)
    job = get_object_or_404(AnalysisJob, project=project)

    # Redirect to status if not completed
    if job.status != 'completed':
        return redirect('analyzer:project_status', project_id=project.id)

    outputs = {
        output.output_type: output.content
        for output in ProjectOutput.objects.filter(project=project)
    }

    file_summaries = FileSummary.objects.filter(project=project).order_by('file_path')
    module_summaries = ModuleSummary.objects.filter(project=project).order_by('module_path')

    return render(request, 'analyzer/results.html', {
        'project': project,
        'job': job,
        'outputs': outputs,
        'file_summaries': file_summaries,
        'module_summaries': module_summaries,
    })


@require_POST
def cancel_project(request, project_id):
    """Cancel a pending or processing analysis job."""
    project = get_object_or_404(Project, id=project_id)
    job = get_object_or_404(AnalysisJob, project=project)

    if job.status not in ['completed', 'failed']:
        job.status = 'cancelled'
        job.progress_message = 'Analysis cancelled by user.'
        job.save(update_fields=['status', 'progress_message'])
    
    return redirect('analyzer:project_status', project_id=project.id)


@require_POST
def restart_project(request, project_id):
    """Restart a cancelled or failed analysis job, wiping previous results."""
    project = get_object_or_404(Project, id=project_id)
    job = get_object_or_404(AnalysisJob, project=project)

    # Clear previous output
    FileSummary.objects.filter(project=project).delete()
    ModuleSummary.objects.filter(project=project).delete()
    ProjectOutput.objects.filter(project=project).delete()

    job.status = 'pending'
    job.progress_percent = 0
    job.progress_message = 'Job restarted, waiting to start...'
    job.error_message = ''
    job.completed_at = None
    job.save()

    # Dispatch the task
    if settings.USE_CELERY:
        task = analyze_project.delay(str(job.id))
        job.celery_task_id = task.id
    else:
        background_queue.enqueue(analyze_project, str(job.id))
        job.celery_task_id = "local-queue"
        
    job.save(update_fields=['celery_task_id'])

    return redirect('analyzer:project_status', project_id=project.id)


@login_required
@require_POST
def resume_project(request, project_id):
    """Resume a cancelled or failed analysis job, keeping previous progress."""
    project = get_object_or_404(Project, id=project_id, user=request.user)
    job = get_object_or_404(AnalysisJob, project=project)

    job.status = 'pending'
    job.progress_message = 'Job resuming, checking existing progress...'
    job.error_message = ''
    job.completed_at = None
    job.save()

    # Dispatch the task
    if settings.USE_CELERY:
        task = analyze_project.delay(str(job.id))
        job.celery_task_id = task.id
    else:
        background_queue.enqueue(analyze_project, str(job.id))
        job.celery_task_id = "local-queue"
        
    job.save(update_fields=['celery_task_id'])

    return redirect('analyzer:project_status', project_id=project.id)


@login_required
@require_GET
def project_list(request):
    """List all projects for the current user."""
    projects = Project.objects.filter(user=request.user).select_related('analysis_job')
    return render(request, 'analyzer/project_list.html', {'projects': projects})


def login_view_ui(request):
    """Render the Custom Login Template (JS driven for OTP)"""
    return render(request, 'analyzer/login.html')

def register_view_ui(request):
    """Render the Custom Register Template (JS driven for OTP)"""
    return render(request, 'analyzer/register.html')


# ──────────────────────────────────────────────
# JSON API Endpoints
# ──────────────────────────────────────────────

@csrf_exempt
@login_required
@require_http_methods(["GET", "POST"])
def api_upload(request):
    """
    API endpoint for uploading a project.

    Accepts:
    - Multipart form data with a ZIP file
    - JSON body with a git_url

    Returns JSON with project_id and job_id.
    """
    content_type = request.content_type or ''

    if 'multipart/form-data' in content_type:
        # ZIP file upload
        zip_file = request.FILES.get('zip_file')
        project_name = request.POST.get('project_name', '')

        if not zip_file:
            return JsonResponse({'error': 'No ZIP file provided'}, status=400)

        if not zip_file.name.lower().endswith('.zip'):
            return JsonResponse({'error': 'Only ZIP files are accepted'}, status=400)

        if not project_name:
            project_name = zip_file.name.rsplit('.', 1)[0]

        project = Project.objects.create(
            name=project_name,
            upload_type='zip',
            source_file=zip_file,
        )
    elif 'application/json' in content_type:
        # Git URL
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON body'}, status=400)

        git_url = body.get('git_url', '')
        project_name = body.get('project_name', '')

        if not git_url:
            return JsonResponse({'error': 'No git_url provided'}, status=400)

        if not project_name:
            project_name = git_url.rstrip('/').rsplit('/', 1)[-1].replace('.git', '')

        project = Project.objects.create(
            name=project_name,
            upload_type='git',
            source_url=git_url,
        )
    else:
        return JsonResponse(
            {'error': 'Unsupported content type. Use multipart/form-data or application/json.'},
            status=400,
        )

    # Create and dispatch job
    job = AnalysisJob.objects.create(
        project=project,
        status='pending',
        progress_message='Job created, waiting to start...',
    )

    if settings.USE_CELERY:
        task = analyze_project.delay(str(job.id))
        job.celery_task_id = task.id
    else:
        background_queue.enqueue(analyze_project, str(job.id))
        job.celery_task_id = "local-queue"
        
    job.save(update_fields=['celery_task_id'])

    return JsonResponse({
        'project_id': str(project.id),
        'job_id': str(job.id),
        'status': 'pending',
        'message': f'Analysis job created for project: {project.name}',
    }, status=201)


@require_GET
def api_status(request, project_id):
    """
    API endpoint to check the analysis status.

    Returns JSON with status, progress, and messages.
    """
    project = get_object_or_404(Project, id=project_id)
    job = get_object_or_404(AnalysisJob, project=project)

    return JsonResponse({
        'project_id': str(project.id),
        'project_name': project.name,
        'status': job.status,
        'progress_percent': job.progress_percent,
        'progress_message': job.progress_message,
        'error_message': job.error_message if job.status == 'failed' else '',
        'started_at': job.started_at.isoformat() if job.started_at else None,
        'completed_at': job.completed_at.isoformat() if job.completed_at else None,
        'total_files': project.total_files,
    })


@require_GET
def api_results(request, project_id):
    """
    API endpoint to fetch analysis results.

    Returns JSON with all generated outputs, file summaries, and module summaries.
    """
    project = get_object_or_404(Project, id=project_id)
    job = get_object_or_404(AnalysisJob, project=project)

    if job.status != 'completed':
        return JsonResponse({
            'error': 'Analysis not yet completed',
            'status': job.status,
            'progress_percent': job.progress_percent,
        }, status=400)

    outputs = {
        output.output_type: output.content
        for output in ProjectOutput.objects.filter(project=project)
    }

    file_summaries = [
        {
            'file_path': fs.file_path,
            'language': fs.language,
            'summary': fs.summary,
            'file_size': fs.file_size,
        }
        for fs in FileSummary.objects.filter(project=project).order_by('file_path')
    ]

    module_summaries = [
        {
            'module_path': ms.module_path,
            'summary': ms.summary,
            'file_count': ms.file_count,
        }
        for ms in ModuleSummary.objects.filter(project=project).order_by('module_path')
    ]

    return JsonResponse({
        'project_id': str(project.id),
        'project_name': project.name,
        'outputs': outputs,
        'file_summaries': file_summaries,
        'module_summaries': module_summaries,
    })


@require_GET
def api_projects(request):
    """
    API endpoint to list all analyzed projects.
    """
    projects = []
    for p in Project.objects.all():
        job = getattr(p, 'analysis_job', None)
        projects.append({
            'project_id': str(p.id),
            'name': p.name,
            'upload_type': p.upload_type,
            'status': job.status if job else 'unknown',
            'total_files': p.total_files,
            'created_at': p.created_at.isoformat(),
        })

    return JsonResponse({'projects': projects})
