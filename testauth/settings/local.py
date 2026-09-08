import django_redis
from allianceauth.authentication.task_statistics.helpers import _RedisStub

from .base import *  # noqa: F403

# Alliance Auth's dashboard counters ask django-redis for a raw connection during
# app startup. Unit tests use an in-memory cache, so provide AA's own no-op stub.


class _TestRedisStub(_RedisStub):
    def ping(self):
        return True

    def info(self):
        return {"redis_version": "8.0.0"}


django_redis.get_redis_connection = lambda alias="default": _TestRedisStub()

INSTALLED_APPS = ["eve_sde"] + INSTALLED_APPS  # noqa: F405
INSTALLED_APPS += ["incursionstatus"]  # noqa: F405

ROOT_URLCONF = "testauth.urls"
SITE_URL = "https://example.test"
CSRF_TRUSTED_ORIGINS = [SITE_URL]
ESI_SSO_CALLBACK_URL = f"{SITE_URL}/sso/callback"
ESI_SSO_CLIENT_ID = "test-client"
ESI_SSO_CLIENT_SECRET = "test-secret"
ESI_USER_CONTACT_EMAIL = "admin@example.test"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "incursion-status-tests",
    }
}

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
CELERY_TASK_ALWAYS_EAGER = True
