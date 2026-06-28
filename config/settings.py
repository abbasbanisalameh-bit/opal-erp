"""
Django settings for Opal School Management System.
"""

from pathlib import Path

# -------------------------
# المسارات
# -------------------------
BASE_DIR = Path(__file__).resolve().parent.parent


# -------------------------
# الأمان
# -------------------------
SECRET_KEY = "django-insecure-akrenm=s^o&3mx#gbk79h4%1+6qhd-%it9zt$##wbm(c0xh_02"

DEBUG = True

ALLOWED_HOSTS = [
    "Opalschool2016.pythonanywhere.com",
    "opalschool2016.pythonanywhere.com",
    "localhost",
    "127.0.0.1",
]


# -------------------------
# التطبيقات
# -------------------------
INSTALLED_APPS = [
    'attendance_v2',
    'parent_portal',
    'accounting',
    'exams',
    'documents',
    'announcements',
    'admissions',
    'academics',
    'core',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'dashboard',
    'accounts',
    'students',
    'teachers',
    'timetable',
    'curriculum',
    'attendance',
    'finance',
]


# -------------------------
# Middleware
# -------------------------
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


ROOT_URLCONF = 'config.urls'


# -------------------------
# Templates
# -------------------------
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'announcements.context_processors.active_announcement',
            ],
        },
    },
]


WSGI_APPLICATION = 'config.wsgi.application'


# -------------------------
# قاعدة البيانات
# -------------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# -------------------------
# كلمات المرور
# -------------------------
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# -------------------------
# اللغة والتوقيت
# -------------------------
LANGUAGE_CODE = 'ar'

TIME_ZONE = 'Asia/Amman'

USE_I18N = True

USE_TZ = True


# -------------------------
# الملفات الثابتة
# -------------------------
STATIC_URL = 'static/'

STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

STATIC_ROOT = BASE_DIR / 'staticfiles'


# -------------------------
# ملفات الوسائط
# -------------------------
MEDIA_URL = '/media/'

MEDIA_ROOT = BASE_DIR / 'media'


# -------------------------
# المفتاح الافتراضي
# -------------------------
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

CSRF_TRUSTED_ORIGINS = [
    "https://opalschool2016.pythonanywhere.com",
]
