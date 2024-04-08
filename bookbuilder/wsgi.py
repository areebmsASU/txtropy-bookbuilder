"""
WSGI config for django_scripts project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

exec(open("/home/bitnami/vars.py").read())

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bookbuilder.settings")

application = get_wsgi_application()
