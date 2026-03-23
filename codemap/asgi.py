"""
ASGI config for the CodeMap project.
"""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'codemap.settings')

application = get_asgi_application()
