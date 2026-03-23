"""
WSGI config for the CodeMap project.
"""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'codemap.settings')

application = get_wsgi_application()
