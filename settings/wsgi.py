"""
WSGI config for settings project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application
from settings.conf import BLOG_ENV_ID
os.environ.setdefault('DJANGO_SETTINGS_MODULE', f'settings.env.{BLOG_ENV_ID}',)

application = get_wsgi_application()
