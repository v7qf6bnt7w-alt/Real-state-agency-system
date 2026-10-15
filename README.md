# Estate North

A Django + Django REST Framework real estate platform. It includes a public responsive listing catalogue, a branded Estate North staff workspace, token-authenticated APIs, mandatory email/phone OTP for staff API sign-in, listing/media/floor-plan management, lead capture/export, and optional Celery notifications.

## Project layout

```text
config/                 Django settings, URLs, ASGI/WSGI and Celery
properties/             Models, serializers, API views, services, tasks and admin
templates/index.html    Responsive public catalogue and lead form
templates/admin/        Estate North-branded staff admin and dashboard
static/css/site.css     Public UI styles
static/css/admin.css    Matching staff admin theme
static/js/site.js       Search, lead submission and interactive floor-plan hotspots
manage.py
requirements.txt
.env.example
```

## Local development

Requires Python 3.10+ and pip. SQLite and Django's console email backend are the local defaults.

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py makemigrations properties
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

The public site is at `/`, staff admin at `/admin/`, interactive API docs at `/docs/` (OpenAPI JSON at `/api/schema/`), and API endpoints under `/api/`. Settings load the `.env` file for local development. Configure an actual SMTP service before enabling OTP for staff. For phone delivery, configure the SMS gateway adapter described below. The development SMS adapter logs a mock delivery event; do not use it for production.

## Core data model

- `User`: email-first staff account with phone, Django password hashing, groups and permissions.
- `Property`: listing details, indexed status/location, prices, specs and amenities.
- `Media`: multiple image/video/brochure file or external video URL records per listing.
- `FloorPlan`: uploaded plan with normalized 0–100 percentage room hotspots in JSON.
- `Lead`: property inquiry plus tracked contact status.
- `LoginOTP`: expiring, one-use, hashed OTP challenges with attempt limits.

Property CRUD is staff-only; public listing reads include only published records. List filters include `property_type`, `status`, `city`, exact `bedrooms` / `bathrooms`, minimum `min_bedrooms` / `min_bathrooms`, `min_price`, `max_price`, and `search`. The public catalogue has selectable price, bedroom and bathroom ranges. Manage listing assets through staff-only CRUD endpoints `/api/media/` and `/api/floor-plans/`; use multipart form data with the listing `property` UUID for uploads. Upload accepted extensions are JPG/JPEG, PNG, WebP, MP4, WebM, PDF, DOCX and SVG; individual files are limited to 25 MB. Floor-plan hotspots are objects such as:

```json
{"label":"Kitchen","x":12,"y":20,"width":23,"height":18,"details":"Island kitchen, 14 m²"}
```

## API quick reference

| Method | Endpoint | Access | Purpose |
|---|---|---|---|
| POST | `/api/auth/otp/start/` | Public, throttled | Validate staff password and send OTP |
| POST | `/api/auth/otp/verify/` | Public, throttled | Verify OTP and return DRF token |
| POST | `/api/auth/logout/` | Staff token | Revoke the current API token |
| GET | `/api/properties/` | Public | Published listings and filters |
| GET | `/api/properties/{uuid}/` | Public | Listing details, media and floor plans |
| POST/PATCH/DELETE | `/api/properties/` or `/{uuid}/` | Staff token | Manage listings |
| POST | `/api/media/`, `/api/floor-plans/` | Staff token | Create media/floor plans (CRUD at detail routes) |
| POST | `/api/leads/public/` | Public, throttled | Submit inquiry (reCAPTCHA when enabled) |
| GET | `/api/leads/` | Staff token | Search/filter inquiries |
| PATCH | `/api/leads/{id}/status/` | Staff token | Set `new`, `contacted`, `in_progress` or `closed` |
| GET | `/api/leads/export/` | Staff token | Export inquiries as CSV |
| GET | `/api/config/` | Public | Public WhatsApp/reCAPTCHA configuration |

Use `Authorization: Token <token>` for staff API requests. Tokens expire after 12 hours by default (`API_TOKEN_TTL_HOURS`) and can be revoked using logout. Django admin accounts and all staff API users must pass OTP; create staff accounts with `createsuperuser` or through the admin. OTPs expire after ten minutes, are single-use, stored hashed, and allow at most five verification attempts.

## Production configuration

Set `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=false`, `DJANGO_ALLOWED_HOSTS`, and a PostgreSQL `DATABASE_URL` in the deployment environment. Configure SMTP, `CORS_ALLOWED_ORIGINS`, HTTPS, `RECAPTCHA_SECRET_KEY` and `RECAPTCHA_SITE_KEY`; production requires reCAPTCHA by default. Redis backs rate-limit caching outside development. Set `AWS_STORAGE_BUCKET_NAME` (and region/credentials via the cloud runtime) to use S3-compatible media storage instead of local `media/`. Keep credentials out of source control.

Set `CELERY_BROKER_URL` to Redis and run `celery -A config worker -l INFO` for asynchronous lead notifications; set `ADMIN_EMAILS` to receive lead alerts. Local development runs tasks eagerly by default. Staff OTP delivery uses email and a development SMS mock. For production phone OTP, configure `SMS_PROVIDER_URL` and optional `SMS_PROVIDER_TOKEN` for a JSON POST adapter accepting `to` and `message`, or replace `send_login_code` in `properties/services.py` with the provider SDK. WhatsApp click-to-chat is exposed through `/api/config/` and works in the UI when `WHATSAPP_NUMBER` is configured.

Use a reverse proxy with request/file-size limits and malware scanning for uploads. Keep media storage private as appropriate and serve uploaded documents with safe content disposition.
