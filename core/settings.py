from pathlib import Path
from decouple import config   # pip install python-decouple

BASE_DIR = Path(__file__).resolve().parent.parent
from dotenv import load_dotenv
import os

load_dotenv()
# ── Security ──────────────────────────────────────────────────────────────────
SECRET_KEY = config('SECRET_KEY')
DEBUG       = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',')


# ── Applications ──────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # third-party
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',

    # local
    'profiles',
    'system',
]

# ── Custom user model ─────────────────────────────────────────────────────────
AUTH_USER_MODEL = 'profiles.User'


# ── Middleware ────────────────────────────────────────────────────────────────
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',          # ← must be first
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# ── URL / WSGI ────────────────────────────────────────────────────────────────
ROOT_URLCONF = 'core.urls'
WSGI_APPLICATION = 'core.wsgi.application'


# ── Templates ────────────────────────────────────────────────────────────────
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


# ── Database ──────────────────────────────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME':     config('DB_NAME'),
        'USER':     config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST':     config('DB_HOST', default='localhost'),
        'PORT':     config('DB_PORT', default='5432'),
    }
}

# ── Password validation ───────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ── Internationalisation ──────────────────────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE     = 'Asia/Manila'  
USE_I18N = True
USE_TZ   = True


# ── Static files ──────────────────────────────────────────────────────────────
STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ── Django REST Framework ─────────────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}


# ── CORS ──────────────────────────────────────────────────────────────────────
# Allows your Vite dev server to talk to Django
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:5173,http://127.0.0.1:5173'
).split(',')

CORS_ALLOW_CREDENTIALS = True


# ── Email (Gmail SMTP) ────────────────────────────────────────────────────────
EMAIL_BACKEND       = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST          = 'smtp.gmail.com'
EMAIL_PORT          = 587
EMAIL_USE_TLS       = True
EMAIL_HOST_USER     = config('EMAIL_HOST_USER')       # your gmail address
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')   # your gmail app password
DEFAULT_FROM_EMAIL  = config('DEFAULT_FROM_EMAIL', default=EMAIL_HOST_USER)


# ── Frontend URL (used in verification emails) ────────────────────────────────
FRONTEND_URL = config('FRONTEND_URL', default='http://localhost:5173')