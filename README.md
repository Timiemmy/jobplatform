# Job Board API

A production-grade, API-first job board platform built with Django REST Framework.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | Django 4.2 + DRF 3.15 |
| Auth | SimpleJWT + dj-rest-auth |
| Database | PostgreSQL 15 |
| Cache / Broker | Redis 7 |
| Async Tasks | Celery 5 |
| API Docs | drf-spectacular (OpenAPI 3) |

---

## Project Structure

```
jobboard/
├── apps/                   # Domain models, services, selectors, signals
│   ├── accounts/           # User model, auth business logic
│   ├── profiles/           # Profile model (1-to-1 with User)
│   ├── jobs/               # Job listings (Phase 2)
│   ├── applications/       # Job applications (Phase 3)
│   └── notifications/      # Async notifications (Phase 3)
│
├── api/
│   └── v1/                 # Versioned API layer — serializers + views + urls
│       └── accounts/
│
├── config/
│   ├── settings/
│   │   ├── base.py         # Shared settings
│   │   ├── dev.py          # Development overrides
│   │   └── prod.py         # Production hardening
│   ├── urls.py             # Root URL config
│   └── wsgi.py
│
├── core/                   # Shared infrastructure
│   ├── models.py           # BaseModel (UUID PK + timestamps)
│   ├── exceptions.py       # Custom exception handler + domain exceptions
│   ├── pagination.py       # StandardPageNumberPagination
│   ├── permissions.py      # Role-based permission classes
│   └── throttles.py        # Rate limit throttle classes
│
├── infrastructure/
│   ├── tasks/              # Celery app instance
│   ├── email/              # Email abstraction (Phase 3)
│   └── storage/            # Cloud storage abstraction (Phase 3)
│
└── tests/                  # Full test suite
    ├── factories.py         # Shared test data factories
    ├── accounts/            # Accounts service, selector, and view tests
    └── core/                # Core infrastructure tests
```

---

## Roles

| Role | Permissions |
|---|---|
| `job_seeker` | Search jobs, apply to jobs, manage own profile |
| `recruiter` | Post/manage jobs, view applicants, update application status |
| `admin` | Full platform access |

---

## API Endpoints — Phase 1

| Method | Endpoint | Auth Required | Description |
|---|---|---|---|
| POST | `/api/v1/auth/register/` | No | Register a new user |
| POST | `/api/v1/auth/login/` | No | Login, receive JWT pair |
| POST | `/api/v1/auth/logout/` | Yes | Blacklist refresh token |
| POST | `/api/v1/auth/token/refresh/` | No | Rotate access token |
| GET | `/api/v1/auth/user/` | Yes | Get current user details |

### API Documentation
- Swagger UI: `http://localhost:8000/api/docs/`
- ReDoc: `http://localhost:8000/api/redoc/`
- OpenAPI JSON: `http://localhost:8000/api/schema/`

---

## Local Development Setup

### Option A — Docker Compose (recommended)

```bash
# 1. Clone and enter the project
git clone <repo-url> && cd jobboard

# 2. Create your .env file from the template
cp .env.example .env
# Edit .env and set SECRET_KEY at minimum

# 3. Start all services (Postgres, Redis, Django, Celery)
docker-compose up --build

# 4. The API is now live at http://localhost:8000
```

### Option B — Local Python environment

**Prerequisites:** Python 3.11+, PostgreSQL 15, Redis 7

```bash
# 1. Create and activate a virtual environment
python -m venv venv && source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up your environment
cp .env.example .env
# Edit .env — minimum required: SECRET_KEY, DATABASE_URL

# 4. Run migrations
python manage.py migrate

# 5. Create a superuser (admin role)
python manage.py createsuperuser

# 6. Start the development server
python manage.py runserver

# 7. Start the Celery worker (separate terminal)
celery -A config worker --loglevel=info
```

---

## Running Tests

```bash
# Run the full test suite
python manage.py test tests

# Run a specific test module
python manage.py test tests.accounts.test_views

# Run a specific test class
python manage.py test tests.accounts.test_views.TestRegisterView

# Run a specific test
python manage.py test tests.accounts.test_views.TestRegisterView.test_successful_registration_returns_201

# With pytest (if installed)
pytest

# With pytest — stop on first failure
pytest -x

# With pytest — show print output
pytest -s
```

---

## Authentication Flow

```
1. Register:   POST /api/v1/auth/register/
               → Returns { user, access, refresh }

2. Use API:    Include header:  Authorization: Bearer <access_token>
               Access token expires in 15 minutes.

3. Refresh:    POST /api/v1/auth/token/refresh/
               Body: { "refresh": "<refresh_token>" }
               → Returns new { access, refresh }
               Refresh token expires in 7 days.
               Old refresh token is blacklisted (ROTATE_REFRESH_TOKENS=True).

4. Logout:     POST /api/v1/auth/logout/
               Body: { "refresh": "<refresh_token>" }
               → Blacklists the refresh token. Client must discard access token.
```

---

## Error Response Shape

All errors return a consistent envelope:

```json
{
    "error": true,
    "message": "Human-readable summary of the error.",
    "detail": { "field": ["Specific validation error."] },
    "code": "validation_error"
}
```

---

## Build Phases

| Phase | Status | Scope |
|---|---|---|
| **Phase 1** | ✅ Complete | Project scaffold, auth, JWT, roles, core infrastructure |
| **Phase 2** | 🔜 Next | Jobs CRUD with search/filter, Profiles |
| **Phase 3** | Planned | Applications workflow, file uploads, async emails |
| **Phase 4** | Planned | Rate limiting, caching, security hardening, full test coverage |

---

## Environment Variables Reference

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes | Django secret key |
| `DEBUG` | No | `True` for dev, `False` for prod |
| `ALLOWED_HOSTS` | Yes | Comma-separated list |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `REDIS_URL` | Yes | Redis connection string |
| `EMAIL_BACKEND` | No | Django email backend class |
| `DEFAULT_FROM_EMAIL` | No | From address for sent emails |
| `AWS_ACCESS_KEY_ID` | Phase 3 | S3 storage credentials |
| `AWS_SECRET_ACCESS_KEY` | Phase 3 | S3 storage credentials |
| `AWS_STORAGE_BUCKET_NAME` | Phase 3 | S3 bucket for resume uploads |
