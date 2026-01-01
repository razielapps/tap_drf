#!/usr/bin/env python3

import os
import sys
import subprocess
from pathlib import Path
import secrets
import string
import shutil
from datetime import datetime
# ------------------------
# Config
# ------------------------
PROJECT_REQUIREMENTS = [
    "django>=4.2",
    "djangorestframework",
    "djangorestframework-simplejwt",
    "django-cors-headers",
    "python-dotenv",
    "django-jet-reboot",
    "drf-yasg",
    "gunicorn",
    "whitenoise",
]

API_APP = "api"
year = datetime.now().year

# ------------------------
# Helpers
# ------------------------
def run(cmd, cwd=None):
    print(f"→ Running: {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=cwd)
    if result.returncode != 0:
        print(f"❌ Command failed: {cmd}")
        sys.exit(1)


def generate_secret_key():
    chars = string.ascii_letters + string.digits + "!@#$%^&*(-_=+)"
    return "".join(secrets.choice(chars) for _ in range(50))


def write_file(path, content):
    path.write_text(content.strip() + "\n")


def get_system_python():
    python = shutil.which("python3") or shutil.which("python")
    if not python:
        raise RuntimeError("Python not found! Install python3 or add python to PATH.")
    return python


def get_venv_python(base):
    """Detect correct venv python executable"""
    if os.name == "nt":
        venv_python = base / "venv" / "Scripts" / "python.exe"
    else:
        venv_python = base / "venv" / "bin" / "python3"
        if not venv_python.exists():
            venv_python = base / "venv" / "bin" / "python"
    if not venv_python.exists():
        raise RuntimeError(f"Python executable not found in venv: {venv_python}")
    return venv_python


# ------------------------
# Main Bootstrap
# ------------------------
def main():
    if len(sys.argv) != 2:
        print("Usage: python bootstrap_drf.py <project_name>")
        sys.exit(1)

    project = sys.argv[1]
    base = Path.cwd() / project
    base.mkdir(parents=True, exist_ok=True)
    os.chdir(base)  # critical for venv creation
    print(f"Project folder created at: {base}")

    secret = generate_secret_key()
    SYSTEM_PYTHON = get_system_python()

    # Step 1: Create virtual environment
    run(f"{SYSTEM_PYTHON} -m venv venv")
    VENV_PYTHON = get_venv_python(base)

    # Step 2: Upgrade pip + install dependencies
    run(f"{VENV_PYTHON} -m pip install --upgrade pip")
    run(f"{VENV_PYTHON} -m pip install {' '.join(PROJECT_REQUIREMENTS)}")

    # Step 3: Create Django project
    run(f"{VENV_PYTHON} -m django startproject {project} .")

    # Step 4: Create API app
    run(f"{VENV_PYTHON} manage.py startapp {API_APP}")

    # Step 5: Write .env
    write_file(
        base / ".env",
        f"""
SECRET_KEY={secret}
DEBUG=True

ALLOWED_HOSTS=*
""",
    )

    # Step 6: requirements.txt
    write_file(base / "requirements.txt", "\n".join(PROJECT_REQUIREMENTS))

    # Step 7: settings.py (safe concatenation to avoid syntax errors)
    settings_content = (
        f"""
from pathlib import Path
import os
from dotenv import load_dotenv
from datetime import timedelta

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("SECRET_KEY")
DEBUG = os.getenv("DEBUG") == "True"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS","").split(",")

INSTALLED_APPS = [
    "jet",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "drf_yasg",
    "{API_APP}",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

CORS_ALLOW_ALL_ORIGINS = True

ROOT_URLCONF = "{project}.urls"

TEMPLATES = [{{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {{
        "context_processors": [
            "django.template.context_processors.debug",
            "django.template.context_processors.request",
            "django.contrib.auth.context_processors.auth",
            "django.contrib.messages.context_processors.messages",
        ],
    }},
}}]

WSGI_APPLICATION = "{project}.wsgi.application"

# Default database: SQLite (works out-of-the-box)
DATABASES = {{
    "default": {{
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }}
}}
"""
        + "\n"
        + "# Uncomment below for PostgreSQL configuration\n"
        + "# DATABASES = {\n"
        + "#     'default': {\n"
        + "#         'ENGINE': 'django.db.backends.postgresql',\n"
        + "#         'NAME': os.getenv('DB_NAME'),\n"
        + "#         'USER': os.getenv('DB_USER'),\n"
        + "#         'PASSWORD': os.getenv('DB_PASSWORD'),\n"
        + "#         'HOST': os.getenv('DB_HOST'),\n"
        + "#         'PORT': os.getenv('DB_PORT'),\n"
        + "#     }\n"
        + "# }\n"
        + f"""
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {{
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}}

SIMPLE_JWT = {{
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "AUTH_HEADER_TYPES": ("Bearer",),
}}
"""
    )

    write_file(base / project / "settings.py", settings_content)

    # Step 8: urls.py
    write_file(
        base / project / "urls.py",
        f"""
from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions

schema_view = get_schema_view(
    openapi.Info(
        title="API Service",
        default_version="v1",
        description="Production-ready API docs",
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path("jet/", include("jet.urls", "jet")),
    path("admin/", admin.site.urls),
    path("api/", include("{API_APP}.urls")),
    path("api/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("swagger/", schema_view.with_ui("swagger", cache_timeout=0), name="schema-swagger-ui"),
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
]
""",
    )

    # Step 9: API app urls/views
    write_file(
        base / API_APP / "urls.py",
        """
from django.urls import path
from .views import HealthView

urlpatterns = [
    path("v1/health/", HealthView.as_view()),
]
""",
    )

    write_file(
        base / API_APP / "views.py",
        """
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

class HealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"status": "ok"})
""",
    )

    # Step 10: Docker + deployment files
    write_file(
        base / "Dockerfile",
        f"""
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

RUN python manage.py collectstatic --noinput

CMD ["gunicorn", "{project}.wsgi:application", "--bind", "0.0.0.0:8000"]
""",
    )

    write_file(
        base / "docker-compose.yml",
        """
version: "3.9"

services:
  web:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
""",
    )

    write_file(
        base / ".dockerignore",
        """
.env
venv
__pycache__
*.pyc
db.sqlite3
""",
    )

    write_file(base / "Procfile", f"web: gunicorn {project}.wsgi")
    write_file(base / "runtime.txt", "python-3.11.6")
    write_file(
        base / "LICENSE",
        f"""

MIT License

Copyright (c) {year} Conscience Ekhomwandolor (AVT Conscience)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.""",
    )
    write_file(
        base / "README.md",
        f"""

# {project}
## This project was bootstrapped using [tap_drf](https://github.com/razielapps/tap_drf) - A production-ready Django REST Framework boilerplate with JWT auth, Swagger docs, Docker support, and more.

**Conscience Ekhomwandolor (AVT Conscience)**  
- Passionate  fullstack developer & cyber security researcher (red team enthusiast) 
- Creator of tap_drf, tap_react, tap_fullstack  
- Personal Blog: [https://medium.com/@avtconscience](https://medium.com/@avtconscience)  
- GitHub: [https://github.com/razielapps](https://github.com/razielapps)  
- Email: [avtxconscience@gmail.com](mailto:avtxconscience@gmail.com)

For questions, support, or collaboration, feel free to reach out.


""",
    )
    write_file(
        base / ".gitignore",
        """
.env
/*/__pycache__/
/*/migrations/
/venv/
*.pyc
*.pyo
*.pyd
__pycache__/
*.sqlite3
db.sqlite3
.DS_Store
.idea/
.vscode/
*.log
coverage/
htmlcov/
.tox/
.nox/
.coverage
.coverage.*
.cache
.pytest_cache/
nosetests.xml
coverage.xml
*.cover
*.egg

""",
    )

    write_file(
        base / "README_DEPLOYMENT.md",
        """
# Deployment Guide

## Docker
docker compose up -d

## Heroku
heroku create
heroku config:set SECRET_KEY=...
git push heroku main

## PythonAnywhere / cPanel
- Create virtualenv
- Install requirements
- Set WSGI to project/wsgi.py

## AWS / DigitalOcean / Render
- Use Dockerfile
- Set env vars
""",
    )

    # Step 11: Migrations + superuser
    run(f"{VENV_PYTHON} manage.py migrate")
    run(f"{VENV_PYTHON} manage.py createsuperuser")

    print("\n✅ FULL PLATFORM BOOTSTRAP COMPLETE")
    print("Swagger UI: /swagger/")
    print("ReDoc: /redoc/")
    print("Admin: /admin/")
    print("JWT login: /api/auth/token/")


if __name__ == "__main__":
    main()
