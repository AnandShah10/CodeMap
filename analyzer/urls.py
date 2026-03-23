"""
URL configuration for the Analyzer app.
"""
from django.urls import path

from . import views

app_name = 'analyzer'

urlpatterns = [
    # ── Template Views ───────────────────────────────────
    path('', views.upload_project, name='upload'),
    path('projects/', views.project_list, name='project_list'),
    path('projects/<uuid:project_id>/status/', views.project_status, name='project_status'),
    path('projects/<uuid:project_id>/results/', views.project_results, name='project_results'),

    # ── JSON API Endpoints ───────────────────────────────
    path('api/upload/', views.api_upload, name='api_upload'),
    path('api/projects/', views.api_projects, name='api_projects'),
    path('api/projects/<uuid:project_id>/status/', views.api_status, name='api_status'),
    path('api/projects/<uuid:project_id>/results/', views.api_results, name='api_results'),
]
