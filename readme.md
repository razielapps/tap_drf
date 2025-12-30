


---

# 🔹 tap_drf

## Overview

**tap_drf** is a **one-command Django REST Framework (DRF) project generator**, designed to help developers **instantly create a production-ready API project**.
It automates the creation of a full DRF project with modern tools, deployment-ready configuration, and best practices, allowing your team to **focus entirely on development** instead of setup.

---

## ✅ Key Features

1. **Project Setup**

   * Creates a **Django project** and a dedicated **API app**.
   * Configures **SQLite by default** (no external DB required).
   * Includes a **commented PostgreSQL configuration** for easy migration.

2. **Modern Admin Interface**

   * Integrates **django-jet-reboot** for a **modern, clean admin interface**.
   * Accessible at `/jet/`.

3. **JWT Authentication**

   * Configures **DRF with JWT authentication** using `djangorestframework-simplejwt`.
   * Provides ready-to-use **token endpoints**:

     * `/api/auth/token/` → Obtain access/refresh token
     * `/api/auth/token/refresh/` → Refresh token

4. **API Documentation**

   * Integrates **drf-yasg** for OpenAPI documentation.
   * Swagger UI: `/swagger/`
   * ReDoc: `/redoc/`

5. **Static Files & Whitenoise**

   * Collects static files and serves them via **Whitenoise** for production-ready static management.

6. **Environment Management**

   * Generates a `.env` file with **SECRET_KEY**, **DEBUG**, and **ALLOWED_HOSTS**.

7. **Superuser Creation**

   * Automatically prompts for **superuser creation** after migrations.

8. **Docker & Deployment Ready**

   * Generates **Dockerfile**, **docker-compose.yml**, **.dockerignore**, and **Procfile**.
   * Includes **deployment instructions** for Heroku, PythonAnywhere, cPanel, AWS, DigitalOcean, Render.
   * Supports running locally, in Docker, or on cloud infrastructure.

9. **Health Endpoint**

   * Provides a minimal **`api/v1/health/` endpoint** for testing and monitoring.

10. **Cross-platform Compatible**

    * Works on **Linux, macOS, Windows**.
    * Automatically detects system Python and virtual environment paths.

---

## 💡 Save Hours, Build On-The-Go

* **Instant Project Bootstrap** – Developers no longer waste hours configuring Django, DRF, admin, authentication, or deployment settings.
* **Production-ready Defaults** – Includes static files, Whitenoise, JWT, modern admin, API documentation, and Docker setup.
* **Flexible Database** – Start with SQLite instantly, upgrade to PostgreSQL when needed.
* **Cloud-ready** – Easily deploy to **Heroku, AWS, PythonAnywhere, cPanel**, or Dockerized environments.
* **API-first Development** – Minimal API app structure and Swagger docs make it easy to start building endpoints immediately.
* **Consistency Across Teams** – Ensures every project follows the same modern setup and best practices.

---

## ⚡ Usage

```bash
python tap_drf.py <project_name>
```

* Example:

```bash
python tap_drf.py myproject
```

* This will:

  1. Create the project folder and virtual environment.
  2. Install all required dependencies.
  3. Create a Django project and API app.
  4. Generate `.env` with a secure secret key.
  5. Set up JWT authentication, Jet admin, Swagger/ReDoc.
  6. Prepare Docker and deployment files.
  7. Run migrations and prompt for superuser creation.

---

## 📦 Requirements

* Python 3.10+ installed and accessible via `python3` or `python`.
* Internet connection for package installation.
* Optional: Docker for containerized deployment.

---

## 🚀 After Bootstrap

* **Run locally**:

```bash
source venv/bin/activate       # Linux/macOS
venv\Scripts\activate.bat      # Windows
python manage.py runserver
```

* **Access:**

  * Jet admin → `/jet/`
  * DRF Swagger → `/swagger/`
  * ReDoc → `/redoc/`
  * Health check → `/api/v1/health/`

* **Dockerized run**:

```bash
docker compose up -d
```
## Author

**Conscience Ekhomwandolor (AVT Conscience)**  
- Passionate  fullstack developer & cyber security researcher (red team enthusiast) 
- Creator of tap_drf -a DRF Bootstrap Script for production-ready API development  
- Personal Blog: [https://medium.com/@avtconscience](https://medium.com/@avtconscience)  
- GitHub: [https://github.com/razielapps](https://github.com/razielapps)  
- Email: [avtxconscience@gmail.com](mailto:avtxconscience@gmail.com)

For questions, support, or collaboration, feel free to reach out.

