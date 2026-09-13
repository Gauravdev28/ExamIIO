"""
CODEGUARD — Production Settings
"""
from .base import *

DEBUG = False

# Strict Security Headers & Cookies
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # Allows frontend client to read CSRF token cookie

# Reverse-proxy HTTPS & SSL Redirect
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'True').lower() in ('true', '1', 't')

# Production REST renderer (JSON only)
REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] = [
    'rest_framework.renderers.JSONRenderer',
]

# Phase 9 & Pre-Deployment Hardening: Fail-Closed Production Secret Validation
import re
import sys
from django.core.exceptions import ImproperlyConfigured

is_test_execution = 'pytest' in sys.modules or bool(os.getenv('PYTEST_CURRENT_TEST'))

# 1. SECRET_KEY fail-closed validation
DEV_DEFAULT_SECRET_KEYS = {
    'insecure-default-codeguard-key-must-change-in-prod',
    'django-insecure-change-this-in-production-please-secret-key',
}
if not is_test_execution:
    DEV_DEFAULT_SECRET_KEYS.add('dev-insecure-secret-key-change-in-production-min-50-chars-codeguard-platform-2026')

secret_key = os.getenv('SECRET_KEY')
if not secret_key or not secret_key.strip():
    raise ImproperlyConfigured("SECRET_KEY environment variable is mandatory in production.")

if secret_key.strip() in DEV_DEFAULT_SECRET_KEYS:
    raise ImproperlyConfigured("SECRET_KEY cannot use an insecure development default key in production.")

# 2. DSAR Master Key Fail-Closed Production Security (SEC-03)
DEV_DEFAULT_KEY_V1 = '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
v1_key = os.getenv('DSAR_MASTER_KEY_V1')

if not v1_key:
    raise ImproperlyConfigured("DSAR_MASTER_KEY_V1 environment variable is mandatory in production.")

v1_key_clean = v1_key.strip()

if v1_key_clean == DEV_DEFAULT_KEY_V1:
    raise ImproperlyConfigured("DSAR_MASTER_KEY_V1 cannot use the insecure development default key in production.")

if len(v1_key_clean) != 64 or not re.fullmatch(r'[0-9a-fA-F]{64}', v1_key_clean):
    raise ImproperlyConfigured("DSAR_MASTER_KEY_V1 must be a valid 64-character hexadecimal string (32 bytes).")

# 3. Database & Redis Credentials validation in production
if not is_test_execution:
    if not USE_SQLITE_DEV:
        db_pass = os.getenv('DB_PASSWORD', '').strip()
        if not db_pass or db_pass in ('codeguard_secure_password', 'root_secure_password'):
            raise ImproperlyConfigured("DB_PASSWORD must be configured with a secure production password and cannot use development defaults.")

    redis_pass = os.getenv('REDIS_PASSWORD', '').strip()
    if not redis_pass or redis_pass in ('secure_redis_pass', 'judge0_redis_pass', 'dev_redis_secure_password'):
        raise ImproperlyConfigured("REDIS_PASSWORD must be configured with a secure production password and cannot use development defaults.")

