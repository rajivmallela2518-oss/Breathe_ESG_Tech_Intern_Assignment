# Breathe ESG — Carbon Data Ingestion & Review Platform

A full-stack application that ingests corporate emissions data from three source systems (SAP fuel/procurement, utility electricity, corporate travel), validates and normalises each row against GHG Protocol standards, and surfaces a review queue where an analyst can approve or reject records before they are locked for external audit.

Built as the Breathe ESG Tech Intern Assignment.

---

## Live deployment

| Service | URL |
|---------|-----|
| Frontend | https://breathe-esg-tech-intern-assignment-ashen.vercel.app |
| Backend API | https://breathe-esg-tech-intern-assignment-59eu.onrender.com/api/v1/ |

---

## Stack

```
Browser
  └── React 18 + Vite + Tailwind CSS
        │  JWT in localStorage
        │  axios with request/response interceptors
        ▼
Django 4.2 + Django REST Framework 3.15
  ├── TenantMiddleware (JWT → request.tenant)
  ├── Parse → Validate → Normalise pipeline (synchronous)
  ├── SimpleJWT (tenant_slug + role embedded in token)
  └── PostgreSQL 15 (JSONB for raw rows and audit snapshots)
```

### Backend apps

| App | Responsibility |
|-----|---------------|
| `tenants` | Organisation boundary; tenant model and request middleware |
| `users` | TenantUser (email login, ANALYST / ADMIN roles) |
| `ingestion` | Upload, parse, validate; UploadBatch + RawRow + ValidationFlag |
| `emissions` | Normalisation, unit conversion, EmissionFactor fixtures |
| `reviews` | Analyst approve/reject workflow; ReviewDecision with locking |
| `audit` | Append-only AuditLog with before/after JSONB snapshots |

---

## Repository structure

```
rajiv/
├── backend/
│   ├── config/              Django project settings (base / local / production)
│   ├── api/v1/              URL router — mounts all app endpoints under /api/v1/
│   ├── tenants/             Tenant model + TenantMiddleware + TenantQuerySetMixin
│   ├── users/               TenantUser model + custom JWT serializer
│   ├── ingestion/
│   │   ├── models.py        UploadBatch, RawRow, ValidationFlag
│   │   ├── services/
│   │   │   ├── parsers/     SAPParser, UtilityParser, TravelParser (BaseParser ABC)
│   │   │   ├── parse_service.py      Orchestrates parse → validate → normalise
│   │   │   └── validation_service.py  Rule engine + bulk DB writes
│   │   └── validators/      SAPValidator, UtilityValidator, TravelValidator
│   ├── emissions/
│   │   ├── models.py        EmissionFactor, NormalizedEmission
│   │   ├── fixtures/        emission_factors.json (DEFRA 2023, UBA, CEA, IEA)
│   │   └── services/        scope_classifier, unit_converter, normalization_service
│   ├── reviews/             ReviewDecision model + approve/reject services
│   ├── audit/               AuditLog model + audit_service
│   ├── requirements.txt
│   ├── manage.py
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── pages/           LoginPage, DashboardPage, UploadPage, ReviewPage, AuditPage
│   │   ├── components/      AppShell, Sidebar, TopBar, StatusBadge, ScopeBadge, FlagBadge
│   │   ├── hooks/           useAuth, useUpload, useReviewQueue, useDashboard, useScopeBreakdown
│   │   └── services/        api.js, authService, ingestionService, reviewService, emissionsService
│   ├── .env.example
│   └── package.json
├── data/samples/            Three representative CSV files (one per source type)
├── docs/
│   ├── API.md               REST endpoint reference (15 endpoints, request/response examples)
│   ├── MODEL.md             Data model — every table, field, index, and invariant
│   ├── DECISIONS.md         15 ambiguity resolutions with rationale
│   ├── TRADEOFFS.md         7 deliberate exclusions with production gap analysis
│   └── SOURCES.md           Emission factor citations + format research
└── render.yaml              Render deployment manifest
```

---

## Local development

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 14+ running locally

### 1. Clone and set up the backend

```bash
# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install dependencies
cd backend
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env — at minimum set SECRET_KEY and DB_* values
```

`.env` fields:

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Any 50-character random string |
| `DEBUG` | `True` for local development |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` |
| `DB_NAME` | PostgreSQL database name (create it first) |
| `DB_USER` | PostgreSQL username |
| `DB_PASSWORD` | PostgreSQL password |
| `DB_HOST` | `localhost` |
| `DB_PORT` | `5432` |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173` (Vite dev server) |

### 2. Create the database and run migrations

```bash
# Create the PostgreSQL database (run in psql or pgAdmin)
createdb breathe_esg

# Run Django migrations
python manage.py migrate

# Load emission factor seed data (DEFRA 2023, UBA, CEA, IEA)
python manage.py loaddata emissions/fixtures/emission_factors.json
```

### 3. Create a tenant and first user

The application is multi-tenant. Every user belongs to a tenant, and the tenant slug is embedded in the JWT. Use the Django shell to create the initial tenant and analyst account:

```bash
python manage.py shell
```

```python
from tenants.models import Tenant
from users.models import TenantUser

# Create a tenant
tenant = Tenant.objects.create(name="Demo Corp", slug="demo")

# Create an analyst user
user = TenantUser.objects.create_user(
    email="analyst@democorp.com",
    password="changeme123",
    full_name="Demo Analyst",
    tenant=tenant,
    role="ANALYST",
)
```

### 4. Start the backend

```bash
python manage.py runserver
# API available at http://localhost:8000/api/v1/
# Admin UI at http://localhost:8000/admin/ (create a superuser first if needed)
```

### 5. Set up the frontend

```bash
cd ../frontend
npm install

# Configure environment
cp .env.example .env
# .env contains: VITE_API_BASE_URL=http://localhost:8000/api/v1
# Leave this commented out for local dev — the Vite proxy handles /api routing
```

`.env.example` for local development (the proxy in `vite.config.js` routes `/api` → `localhost:8000`):

```
# VITE_API_BASE_URL=https://your-backend.onrender.com/api/v1
```

```bash
npm run dev
# Frontend available at http://localhost:5173
```

### 6. Upload sample data

Three sample CSV files are included in `data/samples/`:

| File | Source type | What it tests |
|------|-------------|---------------|
| `sap_fuel_procurement.csv` | `SAP_FUEL` | German locale decimals, duplicate rows, negative reversal, outlier, mixed fuel types |
| `utility_electricity.csv` | `UTILITY_ELECTRICITY` | MWh unit error, duplicate invoice, estimated reading, FIT export (filtered), German dates |
| `corporate_travel.csv` | `CORPORATE_TRAVEL` | Missing distance (IATA lookup), travel class multipliers, hotel stays, ground transport, duplicate row |

Log in at `http://localhost:5173/login`, navigate to **Upload Data**, select a source type, and upload the corresponding sample file. The pipeline runs synchronously and returns row counts. Navigate to **Review Queue** to inspect flagged rows and approve or reject them.

---

## Running tests

```bash
cd backend

# Run the full test suite
python manage.py test

# Run tests for a specific app
python manage.py test ingestion
python manage.py test emissions
```

---

## Deployment

### Backend — Render

The repository includes `render.yaml` at the root. To deploy:

1. Connect the repository to a Render account.
2. Render detects `render.yaml` automatically and provisions:
   - A **Web Service** running `gunicorn config.wsgi:application`
   - A **PostgreSQL** database named `breathe-esg-db`
3. Set one environment variable manually in the Render dashboard:
   - `CORS_ALLOWED_ORIGINS` → the deployed Vercel frontend URL (e.g. `https://breathe-esg-frontend.vercel.app`)
4. After the first deploy, run migrations and load fixtures via the Render shell:

```bash
python manage.py migrate
python manage.py loaddata emissions/fixtures/emission_factors.json
```

All other environment variables (`SECRET_KEY`, `DB_*`) are auto-populated from the database add-on and Render's `generateValue` directive in `render.yaml`.

### Frontend — Vercel

1. Import the repository into Vercel.
2. Set the **Root Directory** to `frontend`.
3. Build command: `npm run build` (auto-detected by Vercel).
4. Add one environment variable:
   - `VITE_API_BASE_URL` → `https://breathe-esg-backend.onrender.com/api/v1`
5. Deploy. Vercel serves the Vite build as a static site with global CDN.

---

## Data pipeline

```
POST /api/v1/ingestion/upload/
       │
       ▼
   parse_service.process_upload()
       │
       ├─ SHA-256 hash file → UploadBatch.file_hash
       ├─ Select parser by source_type (SAP / Utility / Travel)
       ├─ parser.parse(file) → [{row_number, raw_data, canonical, checksum}]
       ├─ RawRow.objects.bulk_create(rows)          ← raw_data persisted
       ├─ Attach canonical_data in-memory (not persisted)
       │
       ├─ validation_service.validate_batch()
       │     ├─ Pre-fetch existing checksums (cross-batch dedup)
       │     ├─ Run per-source validator rules on each canonical row
       │     ├─ ValidationFlag.objects.bulk_create(flags)
       │     └─ RawRow bulk-update → VALID / FLAGGED / FAILED
       │
       └─ normalization_service.normalize_batch()
             ├─ classify_*_row() → activity_type + scope
             ├─ unit_converter.convert() → quantity_normalized, unit_normalized
             ├─ EmissionFactor lookup (most recent active factor)
             ├─ kg_co2e = quantity_normalized × factor (× class multiplier for flights)
             ├─ NormalizedEmission.objects.create()
             └─ ReviewDecision.objects.create(status="PENDING")
```

---

## Analyst workflow

```
Upload CSV
    │
    ▼
Review Queue (PENDING)
    ├── Rows sorted: ERROR flags first → WARNING → clean
    ├── Click any row to expand: full flag messages, location, cost centre
    │
    ├── Approve → ReviewDecision.status = APPROVED, is_locked = True
    │              AuditLog: ROW_APPROVED (analyst, IP, before/after state)
    │
    └── Reject  → Requires note (≥ 5 chars)
                  ReviewDecision.status = REJECTED, is_locked = False
                  (row remains correctable — re-upload after source fix)
                  AuditLog: ROW_REJECTED
```

---

## API

Full endpoint reference: [`docs/API.md`](docs/API.md)

Quick reference:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/auth/token/` | Login — returns access + refresh JWT |
| `POST` | `/auth/token/refresh/` | Silent token refresh |
| `POST` | `/ingestion/upload/` | Upload CSV, run full pipeline |
| `GET` | `/ingestion/batches/` | List upload batches |
| `GET` | `/ingestion/batches/<id>/rows/` | Rows for a batch (filterable by status) |
| `GET` | `/ingestion/suspicious/` | All FLAGGED rows across tenant |
| `GET` | `/ingestion/summary/` | Dashboard KPI counts |
| `GET` | `/emissions/scope-breakdown/` | Total kg CO₂e by scope and source type |
| `GET` | `/reviews/?status=PENDING` | Analyst review queue |
| `POST` | `/reviews/<id>/approve/` | Approve and lock a row |
| `POST` | `/reviews/<id>/reject/` | Reject with a mandatory note |
| `GET` | `/audit/` | Chronological audit trail |

---

## Documentation

| Document | Contents |
|----------|----------|
| [`docs/MODEL.md`](docs/MODEL.md) | Every table, field, index, and business invariant |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | 15 ambiguity resolutions — SAP format assumptions, outlier thresholds, dedup algorithm, pipeline architecture, multi-tenancy, locking semantics, Scope 2 method |
| [`docs/TRADEOFFS.md`](docs/TRADEOFFS.md) | 7 deliberate exclusions — market-based Scope 2, Scope 3 completeness, refrigerant emissions, API connectors, correction workflow, reporting export, biogenic carbon |
| [`docs/SOURCES.md`](docs/SOURCES.md) | Emission factor citations (DEFRA 2023 v1.2, UBA, CEA, IEA) and GHG Protocol methodology references |
| [`docs/API.md`](docs/API.md) | REST endpoint reference with request/response examples and flag codes |

---

## Emission factors

Seeded from `backend/emissions/fixtures/emission_factors.json`. All values are from DEFRA 2023 Greenhouse Gas Reporting Conversion Factors v1.2 except where noted.

| Activity | Factor | Unit | Source |
|----------|--------|------|--------|
| Diesel | 2.688 | kg CO₂e / litre | DEFRA 2023 Table 1A |
| Petrol | 2.312 | kg CO₂e / litre | DEFRA 2023 Table 1A |
| Natural gas | 2.043 | kg CO₂e / m³ | DEFRA 2023 Table 1A |
| Biodiesel (FAME) | 0.199 | kg CO₂e / litre | DEFRA 2023 Table 1A |
| UK grid electricity | 0.20705 | kg CO₂e / kWh | DEFRA 2023 Table 12 |
| German grid electricity | 0.366 | kg CO₂e / kWh | UBA 2023 |
| Indian grid electricity | 0.716 | kg CO₂e / kWh | CEA 2022–23 |
| Flight long-haul (with RF) | 0.19085 | kg CO₂e / passenger-km | DEFRA 2023 Table 6 |
| Hotel stay | 31.47 | kg CO₂e / room-night | DEFRA 2023 Table 8 |
| National rail | 0.03549 | kg CO₂e / km | DEFRA 2023 Table 5 |

Full table and citations: [`docs/SOURCES.md`](docs/SOURCES.md)

---

## Assignment requirements checklist

- [x] SAP fuel/procurement data source — parser, validator, normaliser, sample CSV
- [x] Utility electricity data source — parser, validator, normaliser, sample CSV
- [x] Corporate travel data source — parser, validator, normaliser, sample CSV
- [x] Validation engine — 22 flag codes across ERROR / WARNING / INFO severities
- [x] GHG Protocol scope classification (Scope 1 / 2 / 3)
- [x] Unit normalisation — explicit conversion table, no generic library
- [x] Analyst review dashboard — approve / reject with mandatory rejection note
- [x] Audit trail — append-only, before/after JSONB snapshots, IP address
- [x] Multi-tenancy — JWT-embedded tenant slug, middleware enforcement
- [x] Deployed — backend on Render, frontend on Vercel
- [x] MODEL.md — every table documented with invariants
- [x] DECISIONS.md — 15 ambiguity resolutions
- [x] TRADEOFFS.md — 7 deliberate exclusions
- [x] SOURCES.md — full citation chain for all emission factors
