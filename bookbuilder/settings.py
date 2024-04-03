from pathlib import Path
from os import environ

BASE_DIR = Path(__file__).resolve().parent.parent


SECRET_KEY = "django-insecure-6-91u@(y%sy^%nra@gozc@-vhv7u8@2sxas6a5i14#+fol%$kg"

DEBUG = True

ALLOWED_HOSTS = []

INSTALLED_APPS = ["gutenberg.apps.GutenbergConfig"]

ROOT_URLCONF = "bookbuilder.urls"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "bookbuilder",
        "PORT": 5432,
        "HOST": environ.get("DB_HOST"),
        "USER": environ.get("DB_USER"),
        "PASSWORD": environ.get("DB_PASSWORD"),
    },
}


LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
