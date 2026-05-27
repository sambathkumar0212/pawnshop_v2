"""Django settings for pawnshop_management project."""

import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


def env(key, default=None):
    return os.environ.get(key, default)


def env_bool(key, default=False):
    value = os.environ.get(key)
    if value is None:
        return default
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}


def env_int(key, default=0):
    value = os.environ.get(key)
    if value is None or str(value).strip() == '':
        return default
    return int(value)


def env_list(key, default=''):
    value = os.environ.get(key, default)
    return [item.strip() for item in str(value).split(',') if item.strip()]


ENVIRONMENT = env('DJANGO_ENV', 'development').strip().lower()
IS_DEVELOPMENT = ENVIRONMENT == 'development'
IS_PRODUCTION = ENVIRONMENT == 'production'
DEBUG = env_bool('DEBUG', default=IS_DEVELOPMENT)
MINIMAL_STARTUP = env_bool('MINIMAL_STARTUP', default=False)
SKIP_DB_CHECKS = env_bool('SKIP_DB_CHECKS', default=MINIMAL_STARTUP)

try:
    import pawnshop_management.fonts  # noqa: F401
except Exception:
    pass

SECRET_KEY = env('SECRET_KEY', 'django-insecure-development-key')

ALLOWED_HOSTS = env_list(
    'ALLOWED_HOSTS',
    '127.0.0.1,localhost' if DEBUG else '127.0.0.1,localhost,pawnshop-z817.onrender.com,35.224.25.162',
)
if env('GAE_APPLICATION') and '.appspot.com' not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append('.appspot.com')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'rest_framework',
    'rest_framework.authtoken',
    'crispy_forms',
    'crispy_bootstrap5',
    'django_filters',
    'corsheaders',
    'accounts',
    'branches',
    'inventory',
    'transactions',
    'reporting',
    'biometrics',
    'integrations',
    'schemes',
    'gst',
    'analytics',
]

BASE_MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]

MIDDLEWARE = list(BASE_MIDDLEWARE)
if not MINIMAL_STARTUP:
    MIDDLEWARE.insert(0, 'corsheaders.middleware.CorsMiddleware')
    MIDDLEWARE.extend([
        'django.middleware.clickjacking.XFrameOptionsMiddleware',
        'pawnshop_management.middleware.DatabaseConnectionMiddleware',
        'pawnshop_management.middleware.OrganizationDataIsolationMiddleware',
    ])

ROOT_URLCONF = 'pawnshop_management.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'pawnshop_management.wsgi.application'
ASGI_APPLICATION = 'pawnshop_management.asgi.application'

DATABASE_URL = env('DATABASE_URL', '').strip()
DATABASE_ENGINE = env('DATABASE_ENGINE', 'django.db.backends.sqlite3').strip()
DATABASE_NAME = env('DATABASE_NAME', 'db.sqlite3').strip()

if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.parse(DATABASE_URL, conn_max_age=600),
    }
elif DATABASE_ENGINE == 'django.db.backends.sqlite3':
    database_name = Path(DATABASE_NAME)
    if not database_name.is_absolute():
        database_name = BASE_DIR / database_name
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': str(database_name),
            'CONN_MAX_AGE': 0,
            'OPTIONS': {'timeout': 20},
            'TEST': {'NAME': str(BASE_DIR / 'test_db.sqlite3')},
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': DATABASE_ENGINE,
            'NAME': DATABASE_NAME,
            'USER': env('DATABASE_USER', ''),
            'PASSWORD': env('DATABASE_PASSWORD', ''),
            'HOST': env('DATABASE_HOST', ''),
            'PORT': env('DATABASE_PORT', ''),
            'CONN_MAX_AGE': 600,
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 8},
    },
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = env('TIME_ZONE', 'UTC')
USE_I18N = True
USE_L10N = True
USE_TZ = True

LANGUAGES = [
    ('en', 'English'),
    ('ta', 'Tamil'),
]

LOCALE_PATHS = [BASE_DIR / 'locale']

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'accounts.CustomUser'

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
}

CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'
LOGOUT_USING_GET = True

EMAIL_BACKEND = env('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = env('EMAIL_HOST', '')
EMAIL_PORT = env_int('EMAIL_PORT', 25)
EMAIL_USE_TLS = env_bool('EMAIL_USE_TLS', True)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', 'webmaster@localhost')

FACE_RECOGNITION_MODEL = env('FACE_RECOGNITION_MODEL', 'hog')
FACE_RECOGNITION_TOLERANCE = float(env('FACE_RECOGNITION_TOLERANCE', '0.6').split('#')[0].strip())
FACE_IMAGES_DIR = BASE_DIR / 'media' / 'faces'

SECURE_SSL_REDIRECT = env_bool('SECURE_SSL_REDIRECT', default=IS_PRODUCTION and not DEBUG)
SESSION_COOKIE_SECURE = env_bool('SESSION_COOKIE_SECURE', default=IS_PRODUCTION and not DEBUG)
CSRF_COOKIE_SECURE = env_bool('CSRF_COOKIE_SECURE', default=IS_PRODUCTION and not DEBUG)
SECURE_HSTS_SECONDS = env_int('SECURE_HSTS_SECONDS', 31536000 if IS_PRODUCTION and not DEBUG else 0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=IS_PRODUCTION and not DEBUG)
SECURE_HSTS_PRELOAD = env_bool('SECURE_HSTS_PRELOAD', default=IS_PRODUCTION and not DEBUG)
SECURE_CONTENT_TYPE_NOSNIFF = env_bool('SECURE_CONTENT_TYPE_NOSNIFF', True)
SECURE_BROWSER_XSS_FILTER = env_bool('SECURE_BROWSER_XSS_FILTER', True)
X_FRAME_OPTIONS = env('X_FRAME_OPTIONS', 'SAMEORIGIN')

CORS_ALLOW_ALL_ORIGINS = env_bool('CORS_ALLOW_ALL_ORIGINS', False)
CORS_ALLOWED_ORIGINS = env_list(
    'CORS_ALLOWED_ORIGINS',
    'http://10.0.2.2:8000,http://127.0.0.1:8000,http://localhost:8000',
)

DATA_UPLOAD_MAX_MEMORY_SIZE = env_int('DATA_UPLOAD_MAX_MEMORY_SIZE', 26214400)  # 25 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = env_int('FILE_UPLOAD_MAX_MEMORY_SIZE', 26214400)  # 25 MB
