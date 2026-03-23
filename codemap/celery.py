"""
Celery configuration for the CodeMap project.

Uses Redis as the message broker and result backend.
Autodiscovers tasks from all registered Django apps.
"""
import os

from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'codemap.settings')

app = Celery('codemap')

# Read config from Django settings, using the CELERY_ namespace.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Autodiscover tasks.py in all installed apps.
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task that prints the request info."""
    print(f'Request: {self.request!r}')
