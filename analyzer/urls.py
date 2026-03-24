"""
URL configuration for the Analyzer app.
"""
from django.urls import path

from . import views

from . import views
from django.contrib.auth import views as auth_views
from . import api_auth
app_name = 'analyzer'

urlpatterns = [
    # ── Template Views ───────────────────────────────────
    path('upload/', views.upload_project, name='upload'),
    path('', views.landing, name='landing'),
    path('projects/', views.project_list, name='project_list'),
    path('projects/<uuid:project_id>/status/', views.project_status, name='project_status'),
    path('projects/<uuid:project_id>/results/', views.project_results, name='project_results'),
    path('projects/<uuid:project_id>/cancel/', views.cancel_project, name='cancel_project'),
    path('projects/<uuid:project_id>/restart/', views.restart_project, name='restart_project'),
    path('projects/<uuid:project_id>/resume/', views.resume_project, name='resume_project'),

    # ── JSON API Endpoints ───────────────────────────────
    path('api/upload/', views.api_upload, name='api_upload'),
    path('api/projects/', views.api_projects, name='api_projects'),
    path('api/projects/<uuid:project_id>/status/', views.api_status, name='api_status'),
    path('api/projects/<uuid:project_id>/results/', views.api_results, name='api_results'),

    # ── JWT/OTP API Auth Endpoints ──────────────────────
    path('api/auth/signup/', api_auth.signup_api, name='api_signup'),
    path('api/auth/login/', api_auth.login_api, name='api_login'),
    path('api/auth/verify/', api_auth.verify_otp_api, name='api_verify'),
    path('api/auth/resend/', api_auth.resend_otp_api, name='api_resend'),

    # ── Authentication UI Endpoints ─────────────────────────
    path('login/', views.login_view_ui, name='login'), # We will rewrite the view to point to our template
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('register/', views.register_view_ui, name='register'),
]
