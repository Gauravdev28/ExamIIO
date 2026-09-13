import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault(
    'DJANGO_SETTINGS_MODULE',
    'codeguard.settings.production' if os.getenv('DJANGO_ENV') == 'production' else 'codeguard.settings.development'
)

application = get_wsgi_application()
