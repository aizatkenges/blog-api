"""
ASGI config for settings project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

from settings.conf import BLOG_ENV_ID

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    f"settings.env.{BLOG_ENV_ID}",
)

application = get_asgi_application()
