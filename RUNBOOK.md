# Job Board API — Production Runbook

Complete reference for deploying, operating, and troubleshooting
the Job Board API platform in production.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Prerequisites](#2-prerequisites)
3. [Environment Variables](#3-environment-variables)
4. [First-Time Deployment](#4-first-time-deployment)
5. [Running the Stack](#5-running-the-stack)
6. [Running Tests](#6-running-tests)
7. [Database Operations](#7-database-operations)
8. [API Reference](#8-api-reference)
9. [Monitoring & Health](#9-monitoring--health)
10. [Security Checklist](#10-security-checklist)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Architecture Overview

```
Client
  │
  ▼
Nginx / Load Balancer  (TLS termination)
  │
  ▼
Django API (Gunicorn)   ◄──► PostgreSQL
  │
  ├──► Redis  (cache + Celery broker)
  │
  └──► Celery Worker  ──► SMTP / SendGrid  (email delivery)
                      └──► S3             (resume file storage)
```

**Request lifecycle:**
1. Request hits Nginx → forwarded to Gunicorn on port 8000
2. Django processes request through middleware chain
3. View delegates to service layer → ORM → PostgreSQL
4. Response cached in Redis if applicable (job list/detail)
5. Async side-effects (email) enqueued to Redis → picked up by Celery worker

---

## 2. Prerequisites

| Dependency         | Minimum Version | Notes                              |
|--------------------|-----------------|------------------------------------|
| Python             | 3.11+           | 3.12 recommended                   |
| PostgreSQL         | 15+             |                                    |
| Redis              | 7+              | Broker + cache                     |
| Docker + Compose   | 24+             | Local development                  |
| AWS account        | —               | S3 for resume storage (prod only)  |

---

## 3. Environment Variables

Copy `.env.example` to `.env` and populate all values.

### Required in all environments

```bash
SECRET_KEY=<50+ random chars — never reuse across environments>
DATABASE_URL=postgres://user:password@host:5432/dbname
REDIS_URL=redis://host:6379/0
```

### Required in production only

```bash
DEBUG=False
ALLOWED_HOSTS=api.yourdomain.com
CORS_ALLOWED_ORIGINS=https://app.yourdomain.com

# Email (SendGrid recommended)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=SG.xxxxxxxxxxxxxxxx
DEFAULT_FROM_EMAIL=noreply@yourdomain.com

# S3 resume storage
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_STORAGE_BUCKET_NAME=your-bucket-name
AWS_S3_REGION_NAME=us-east-1
```

### Secret key generation

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

---

## 4. First-Time Deployment

### Local development

```bash
# 1. Clone and enter project
git clone <repo-url> && cd jobboard

# 2. Create virtual environment
python -m venv venv && source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy and configure environment
cp .env.example .env
# Edit .env — set DATABASE_URL and REDIS_URL at minimum

# 5. Start backing services
docker-compose up -d db redis

# 6. Run migrations
python manage.py migrate

# 7. Create a superuser
python manage.py createsuperuser

# 8. Start development server
python manage.py runserver

# 9. In a separate terminal — start Celery worker
celery -A config worker --loglevel=info
```

### Docker (full stack)

```bash
# Start all services
docker-compose up -d

# Run migrations inside the container
docker-compose exec api python manage.py migrate

# Create superuser
docker-compose exec api python manage.py createsuperuser

# Tail logs
docker-compose logs -f api celery_worker
```

### Production (bare metal / VM)

```bash
# Install system dependencies (Ubuntu)
apt-get install -y python3.11 python3.11-venv libpq-dev gcc libmagic1

# Set up virtualenv
python3.11 -m venv /opt/jobboard/venv
source /opt/jobboard/venv/bin/activate
pip install -r requirements.txt

# Export production settings
export DJANGO_SETTINGS_MODULE=config.settings.prod

# Run migrations
python manage.py migrate --noinput

# Collect static files
python manage.py collectstatic --noinput

# Start Gunicorn
gunicorn config.wsgi:application \
  --workers 4 \
  --worker-class gthread \
  --threads 2 \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -

# Start Celery worker (separate process / systemd service)
celery -A config worker \
  --loglevel=info \
  --concurrency=4 \
  --queues=default
```

---

## 5. Running the Stack

### Service ports

| Service     | Local Port | Notes                        |
|-------------|------------|------------------------------|
| Django API  | 8000       | `python manage.py runserver` |
| PostgreSQL  | 5432       |                              |
| Redis       | 6379       |                              |
| Celery      | —          | Worker process, no HTTP port |

### Celery commands

```bash
# Start worker (development)
celery -A config worker --loglevel=debug

# Start worker (production)
celery -A config worker --loglevel=info --concurrency=4

# Monitor task queue (requires flower: pip install flower)
celery -A config flower --port=5555

# Purge all pending tasks (use with caution)
celery -A config purge

# Inspect active tasks
celery -A config inspect active
```

---

## 6. Running Tests

```bash
# Run the full test suite
pytest

# Run with coverage report
pytest --cov=. --cov-report=term-missing --cov-report=html

# Run a specific domain
pytest tests/accounts/
pytest tests/jobs/
pytest tests/applications/
pytest tests/security/

# Run a specific test class
pytest tests/security/test_security_audit.py::TestSensitiveFieldExposure

# Run a single test
pytest tests/accounts/test_views.py::TestLoginView::test_valid_credentials_return_200

# Run with verbose output
pytest -v

# Run only fast tests (skip slow marker)
pytest -m "not slow"

# Run with parallel execution (install pytest-xdist)
pytest -n auto
```

### Interpreting test output

- All 21 test files must pass with 0 failures before any deployment.
- The security audit suite (`tests/security/test_security_audit.py`) is the
  critical path — failures here block deployment unconditionally.

---

## 7. Database Operations

### Migrations

```bash
# Create new migration after model changes
python manage.py makemigrations <app_name>

# Apply all pending migrations
python manage.py migrate

# Show migration status
python manage.py showmigrations

# Roll back one migration
python manage.py migrate <app_name> <previous_migration>

# Generate SQL without applying (dry run)
python manage.py sqlmigrate <app_name> <migration_name>
```

### Backup and restore

```bash
# Backup (pg_dump)
pg_dump -h localhost -U postgres jobboard_db > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore
psql -h localhost -U postgres jobboard_db < backup_file.sql
```

---

## 8. API Reference

Base URL: `https://api.yourdomain.com/api/v1/`

Interactive docs: `https://api.yourdomain.com/api/docs/`

### Authentication

All authenticated endpoints require:
```
Authorization: Bearer <access_token>
```

Access tokens expire in **15 minutes**. Refresh tokens expire in **7 days**.
After logout, refresh tokens are blacklisted immediately.

| Endpoint                    | Method | Auth     | Description                  |
|-----------------------------|--------|----------|------------------------------|
| `/auth/register/`           | POST   | None     | Register new user            |
| `/auth/login/`              | POST   | None     | Login, receive JWT pair      |
| `/auth/logout/`             | POST   | Required | Blacklist refresh token      |
| `/auth/token/refresh/`      | POST   | None     | Rotate access token          |
| `/auth/user/`               | GET    | Required | Own user data                |

### Profiles

| Endpoint             | Method | Auth                | Description         |
|----------------------|--------|---------------------|---------------------|
| `/profiles/me/`      | GET    | Any role            | Retrieve own profile|
| `/profiles/me/`      | PATCH  | Any role            | Update own profile  |

### Jobs

| Endpoint               | Method | Auth               | Description                    |
|------------------------|--------|--------------------|--------------------------------|
| `/jobs/`               | GET    | None               | List published jobs            |
| `/jobs/`               | POST   | Recruiter only     | Create job posting             |
| `/jobs/mine/`          | GET    | Recruiter only     | Own job listings               |
| `/jobs/{id}/`          | GET    | None               | Retrieve job detail            |
| `/jobs/{id}/`          | PATCH  | Owner / Admin      | Update job                     |
| `/jobs/{id}/`          | DELETE | Owner / Admin      | Soft-delete job                |
| `/jobs/{id}/applicants/` | GET  | Owner recruiter    | View all applicants for a job  |

### Applications

| Endpoint                          | Method | Auth                | Description                  |
|-----------------------------------|--------|---------------------|------------------------------|
| `/applications/`                  | POST   | Job seeker only     | Apply for a job (multipart)  |
| `/applications/`                  | GET    | Job seeker only     | Own application list         |
| `/applications/{id}/`             | GET    | Application owner   | Application detail           |
| `/applications/{id}/status/`      | PATCH  | Job owner recruiter | Update application status    |
| `/applications/{id}/resume/`      | GET    | Owner / Recruiter   | Get resume download URL      |

### Job search query parameters

```
GET /jobs/?search=python&job_type=full_time&experience_level=senior&location=Lagos&salary_min=50000&salary_max=150000&page=1&page_size=10
```

### Application status lifecycle

```
applied → reviewed → interview → hired
                  ↘             ↘
                   rejected      rejected
```
Terminal statuses (`hired`, `rejected`) cannot be changed.

### Resume upload

```bash
curl -X POST https://api.yourdomain.com/api/v1/applications/ \
  -H "Authorization: Bearer <token>" \
  -F "job_id=<uuid>" \
  -F "resume=@/path/to/resume.pdf" \
  -F "cover_letter=I am very interested in this role."
```

Accepted formats: `.pdf`, `.docx` — Max size: **5 MB**

---

## 9. Monitoring & Health

### Health check

```
GET /health/
```

Returns `200 OK` when all services are reachable, `503` when degraded.

```json
{
  "status": "healthy",
  "checks": {
    "database": "ok",
    "redis":    "ok",
    "celery":   "ok"
  }
}
```

Use this endpoint for:
- Load balancer health probe (every 10s)
- Kubernetes liveness/readiness probe
- Uptime monitoring (PagerDuty, BetterUptime)

### Kubernetes probe config

```yaml
livenessProbe:
  httpGet:
    path: /health/
    port: 8000
  initialDelaySeconds: 15
  periodSeconds: 20

readinessProbe:
  httpGet:
    path: /health/
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
```

### Key metrics to monitor

| Metric                          | Alert threshold   |
|---------------------------------|-------------------|
| API p95 latency                 | > 500ms           |
| API error rate (5xx)            | > 1%              |
| Celery queue depth              | > 100 tasks       |
| Celery task failure rate        | > 5%              |
| Redis memory usage              | > 80%             |
| PostgreSQL connection pool      | > 80% utilised    |
| Resume upload failure rate      | > 2%              |

### Log aggregation

All logs are emitted as JSON to stdout (production).
Ingest into your log aggregator using the `timestamp`, `level`,
`logger`, and `request_id` fields for filtering.

```bash
# Filter errors in the last hour (jq required)
docker logs api 2>&1 | jq 'select(.level == "ERROR")'

# Trace a specific request by ID
docker logs api 2>&1 | jq 'select(.request_id == "550e8400-...")'
```

---

## 10. Security Checklist

Run before every production deployment:

### Pre-deployment

- [ ] `DEBUG=False` in production settings
- [ ] `SECRET_KEY` is unique to this environment (50+ chars)
- [ ] `ALLOWED_HOSTS` is set to the exact domain — no wildcards
- [ ] `CORS_ALLOWED_ORIGINS` is an explicit list — no wildcards
- [ ] All `SECURE_*` settings are enabled (`prod.py`)
- [ ] `SESSION_COOKIE_SECURE=True` and `CSRF_COOKIE_SECURE=True`
- [ ] `ACCOUNT_EMAIL_VERIFICATION="mandatory"`
- [ ] S3 bucket has no public access enabled
- [ ] `AWS_QUERYSTRING_EXPIRE=300` (pre-signed URLs expire in 5 min)
- [ ] Database password is unique and rotated quarterly
- [ ] Redis is not publicly accessible (internal network only)
- [ ] All environment secrets stored in a secret manager (AWS Secrets Manager / Vault)

### Post-deployment

- [ ] `GET /health/` returns `200` with all checks `"ok"`
- [ ] `GET /api/v1/jobs/` returns paginated response
- [ ] Login endpoint returns JWT tokens
- [ ] Protected endpoint with no token returns `401`
- [ ] Protected endpoint with valid token returns expected data
- [ ] Resume upload with `.exe` file returns `400`
- [ ] Resume upload with 6 MB file returns `400`
- [ ] Full test suite passes: `pytest` — 0 failures

### Quarterly security review

- [ ] Rotate `SECRET_KEY` (requires re-login for all users)
- [ ] Rotate AWS credentials
- [ ] Rotate database passwords
- [ ] Review and rotate SendGrid API keys
- [ ] Audit `ALLOWED_HOSTS` and `CORS_ALLOWED_ORIGINS`
- [ ] Review Django and DRF release notes for security patches
- [ ] Run `pip list --outdated` and apply security updates

---

## 11. Troubleshooting

### `500 Internal Server Error` on all requests

1. Check `DEBUG=False` is set — errors won't display in browser.
2. Check logs: `docker-compose logs api | grep ERROR`.
3. Verify database is reachable: `python manage.py dbshell`.
4. Verify Redis is reachable: `redis-cli -u $REDIS_URL ping`.

### Emails not being delivered

1. Check Celery worker is running: `celery -A config inspect ping`.
2. Check Celery queue: `celery -A config inspect active`.
3. Check Redis broker: `redis-cli -u $REDIS_URL llen celery`.
4. Check `EMAIL_HOST_PASSWORD` is set correctly in `.env`.
5. In development, emails print to console — check terminal output.

### `401 Unauthorized` after login

1. Verify the `Authorization: Bearer <token>` header format (note the space).
2. Access token may have expired (TTL: 15 minutes) — use `/auth/token/refresh/`.
3. If refresh also fails, the refresh token may be blacklisted — user must log in again.

### Resume upload fails with `400`

1. Verify file is `.pdf` or `.docx` — no other formats accepted.
2. Verify file size is under 5 MB.
3. Verify `Content-Type: multipart/form-data` is set on the request.
4. Check `python-magic` is installed: `pip show python-magic`.

### Celery tasks not executing

1. Verify Redis is running and `CELERY_BROKER_URL` is correct.
2. Verify the Celery worker process is running.
3. Check for task failures: `celery -A config inspect failed`.
4. Check worker logs for Python import errors on startup.

### Cache returning stale data

1. Manually invalidate: `redis-cli -u $REDIS_URL KEYS "jobboard*" | xargs redis-cli -u $REDIS_URL DEL`.
2. If pattern delete isn't working, verify `django-redis` is installed (not the default cache backend).
3. Check `KEY_PREFIX` in settings matches what's being invalidated.

### Migration conflicts

```bash
# Show current migration state
python manage.py showmigrations

# Detect conflicts
python manage.py makemigrations --check

# Squash migrations if needed (development only)
python manage.py squashmigrations <app_name> <from> <to>
```

---

*Last updated: Phase 4 — Security & Production Hardening*
