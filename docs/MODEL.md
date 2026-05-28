# Data Model

This document describes every table in the Breathe ESG platform: why it exists, what each field means, the invariants that must hold, and the deliberate choices made in the design. It is intended to be read by an auditor, a new engineer, or an evaluator trying to understand the system without running the code.

---

## Domain summary

The platform receives raw operational data from three corporate sources (ERP fuel procurement, utility electricity, and expense management travel), runs it through a validation and normalisation pipeline, and surfaces a review queue where an analyst can approve or reject each computed emission before the data is locked for external audit.

The data lifecycle has four stages that map directly onto four model groups:

```
[source file]
    │
    ▼
UploadBatch + RawRow + ValidationFlag   ← ingestion layer (verbatim source)
    │
    ▼
NormalizedEmission + EmissionFactor     ← emissions layer (computed, unit-normalised)
    │
    ▼
ReviewDecision                          ← review layer (analyst gate)
    │
    ▼
AuditLog                                ← audit layer (append-only record of all changes)
```

Every table also carries a `tenant` FK, enforced by `TenantMiddleware` and `TenantQuerySetMixin`, so no query ever returns rows from a different organisation.

---

## Entity relationship overview

```
Tenant ──< TenantUser
  │
  ├──< UploadBatch ──< RawRow ──< ValidationFlag
  │                      │
  │                      ▼ (1:1)
  │               NormalizedEmission >── EmissionFactor
  │                      │
  │                      ▼ (1:1)
  │               ReviewDecision >── TenantUser (analyst)
  │
  └──< AuditLog >── TenantUser (actor)
                >── ContentType (any object)
```

The one-to-one chain `RawRow → NormalizedEmission → ReviewDecision` is the core structural invariant: every row that can be normalised gets exactly one emission record, and every emission record gets exactly one review decision. The chain is created atomically during the ingestion pipeline.

---

## Table reference

### `tenants_tenant`

The organisational boundary. Every authenticated request resolves to a tenant via the `tenant_slug` claim in the JWT, and every query is filtered by it.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | UUID | PK, `default=uuid4` | Not an integer so tenant IDs cannot be enumerated by incrementing |
| `name` | varchar(255) | NOT NULL | Human-readable display name (e.g. "Acme Corp") |
| `slug` | slug(100) | NOT NULL, UNIQUE | URL-safe identifier embedded in JWT (`tenant_slug` claim); used for routing without an extra DB lookup per request |
| `is_active` | boolean | NOT NULL, default TRUE | Inactive tenants are blocked at middleware; rows are never deleted |
| `created_at` | timestamptz | NOT NULL, auto | |

**Invariant:** `slug` is immutable after creation. Changing it would invalidate all outstanding JWTs.

---

### `users_tenantuser`

Extends Django's `AbstractUser`. `username` is removed; `email` is the login credential.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | UUID | PK | |
| `tenant_id` | UUID | FK → `tenants_tenant`, CASCADE | Hard assignment — users cannot move between tenants |
| `email` | varchar(254) | NOT NULL, UNIQUE (global) | Used as `USERNAME_FIELD`; must be unique across all tenants so Django's auth backend works without a tenant-scoped query |
| `full_name` | varchar(255) | NOT NULL | Embedded in JWT as `full_name` claim |
| `role` | varchar(20) | NOT NULL, default `ANALYST` | `ANALYST` or `ADMIN`; embedded in JWT as `role` claim |
| Inherited password, last_login, is_active, etc. | | | Standard Django auth fields |

**Why email is globally unique:** Django's `authenticate()` takes only `username` (here email) + password. A tenant-scoped unique constraint would require a custom authentication backend that first resolves the tenant. Simpler to require globally unique emails and embed tenant in the token after login.

---

### `ingestion_uploadbatch`

One record per CSV file upload. The batch is the unit of ingestion — files are never partially re-processed.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | UUID | PK | Returned to the frontend immediately so it can poll or navigate |
| `tenant_id` | UUID | FK → `tenants_tenant`, CASCADE | Denormalised here even though it is reachable via `uploaded_by`; avoids a join on every tenant-filtered query |
| `uploaded_by_id` | UUID | FK → `users_tenantuser`, PROTECT | PROTECT so deleting a user does not cascade-delete batches and the rows they produced |
| `source_type` | varchar(30) | NOT NULL, choices | `SAP_FUEL`, `UTILITY_ELECTRICITY`, or `CORPORATE_TRAVEL` — determines which parser and which validator run |
| `original_filename` | varchar(500) | NOT NULL | Preserved for display; has no bearing on processing |
| `file_hash` | varchar(64) | NOT NULL | SHA-256 of the raw file bytes. Used to detect whole-file re-uploads. Not used for row-level deduplication (that uses per-row MD5 checksums) |
| `status` | varchar(20) | NOT NULL, default `PROCESSING` | `PROCESSING` → `COMPLETE` or `FAILED` |
| `total_rows` | integer | NOT NULL, default 0 | Set after parsing; includes all rows including failed |
| `valid_rows` | integer | NOT NULL, default 0 | Rows with no ERROR or WARNING flags |
| `flagged_rows` | integer | NOT NULL, default 0 | Rows with at least one ERROR or WARNING |
| `failed_rows` | integer | NOT NULL, default 0 | Rows that could not be parsed or normalised at all |
| `error_message` | text | nullable | Populated only if batch-level processing fails before any rows are written |
| `created_at` | timestamptz | NOT NULL, auto | |
| `completed_at` | timestamptz | nullable | Set when status transitions to COMPLETE or FAILED |

**Indexes:** `(tenant, status)` for dashboard summary counts; `(tenant, source_type)` for per-source breakdowns; `(file_hash)` for whole-file dedup check.

---

### `ingestion_rawrow`

One record per CSV row, storing the original values verbatim. This table is the source of truth for what was uploaded; it is never modified after creation.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | UUID | PK | |
| `tenant_id` | UUID | FK → `tenants_tenant`, CASCADE | Denormalised — avoids `JOIN ingestion_uploadbatch` on every tenant-filtered query; also makes cross-batch queries (e.g. the duplicate check) efficient with a `(tenant, source_type, status)` index |
| `batch_id` | UUID | FK → `ingestion_uploadbatch`, CASCADE | Cascade is correct: if a batch is deleted its rows are no longer meaningful |
| `row_number` | integer | NOT NULL | 1-based position in the source file; used in flag messages to locate the row |
| `source_type` | varchar(30) | NOT NULL | Copied from the batch at insert time. Denormalised here so `/ingestion/suspicious/` can filter without a join |
| `raw_data` | JSONB | NOT NULL | The original key-value pairs from the CSV, exactly as they appeared (no type coercion). Keys are the source column names (e.g. `MENGE`, `Account_Number`). JSONB rather than text preserves structure and enables key-level queries from psql |
| `status` | varchar(25) | NOT NULL, default `PENDING` | `PENDING` → `VALID`, `FLAGGED`, or `FAILED` after validation |
| `checksum` | varchar(32) | NOT NULL | MD5 hex of `json.dumps(raw_data, sort_keys=True)`. Used for cross-batch row-level deduplication. MD5 is adequate here — this is a business dedup signal, not a cryptographic integrity check; the full `raw_data` is stored for verification |
| `created_at` | timestamptz | NOT NULL, auto | |

**In-memory attribute `canonical_data`:** The parser populates a Python dict on the in-memory object after `bulk_create`. It is never written to the database. The validation and normalisation services read from it during the same request. This avoids storing the parsed intermediate representation alongside the original, which would duplicate data and create a consistency problem if the two ever diverged.

**Indexes:** `(tenant, batch)` for per-batch row listing; `(tenant, status)` for the review queue filter; `(checksum)` for the cross-batch dedup pre-fetch; `(tenant, source_type, status)` for the suspicious rows endpoint.

---

### `ingestion_validationflag`

One record per validation problem found on a row. A row can have zero, one, or many flags. Flags are written in a single `bulk_create` call after all rows in a batch are validated.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | UUID | PK | |
| `tenant_id` | UUID | FK → `tenants_tenant`, CASCADE | Denormalised for consistency with other tables |
| `raw_row_id` | UUID | FK → `ingestion_rawrow`, CASCADE | |
| `flag_code` | varchar(30) | NOT NULL, choices | Machine-readable code (e.g. `DUPLICATE_ROW`, `NEGATIVE_QUANTITY`). The `flag_code` vocabulary is documented in `docs/API.md`. Codes are stable identifiers; the human-readable `message` may change |
| `severity` | varchar(10) | NOT NULL, choices | `ERROR` → row is FLAGGED and must be reviewed; `WARNING` → row is FLAGGED but may be legitimate; `INFO` → row is VALID but carries context the analyst should see |
| `field_name` | varchar(100) | nullable | The column that triggered the flag (e.g. `MENGE`). Null for row-level flags such as statistical outliers |
| `message` | text | NOT NULL | Human-readable explanation shown in the review UI |
| `created_at` | timestamptz | NOT NULL, auto | |

**Row status rule (implemented in `validation_service.py`):**
- If any flag has severity `ERROR` or `WARNING` → row status = `FLAGGED`
- If all flags are `INFO` or there are no flags → row status = `VALID`
- If parsing or normalisation raises an exception → row status = `FAILED`, no flags written

**Indexes:** `(raw_row)` for flag prefetch on row detail; `(tenant, flag_code)` and `(tenant, severity)` for analytics queries.

---

### `emissions_emissionfactor`

The conversion table mapping an activity type and unit to a kg CO₂e figure. Seeded from `backend/emissions/fixtures/emission_factors.json` (DEFRA 2023, UBA, CEA, IEA). No application code writes to this table; updates require a new fixture load or a migration.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | integer | PK (auto) | Integer PK here is intentional: this is a small, stable reference table that is read far more than it is written. UUIDs would not add value |
| `activity_type` | varchar(60) | NOT NULL, choices | Logical activity (e.g. `diesel`, `grid_electricity_uk`, `flight_long_haul`) |
| `scope` | smallint | NOT NULL | GHG Protocol scope: 1 (direct), 2 (purchased electricity), 3 (value-chain) |
| `unit` | varchar(30) | NOT NULL | The normalised unit this factor applies to (e.g. `litre`, `kWh`, `km`, `room_night`) |
| `kg_co2e_per_unit` | decimal(12,8) | NOT NULL | 8 decimal places to preserve sub-milligram precision for low-intensity activities (rail: 0.03549) |
| `source_reference` | varchar(100) | NOT NULL | Citation (e.g. `DEFRA 2023 Table 1A`) |
| `valid_from` | date | NOT NULL | First date this factor applies. The normalisation service selects `ORDER BY valid_from DESC LIMIT 1` so the most recent factor that was valid at ingestion time is used |
| `valid_to` | date | nullable | Open-ended if null. Allows future factors to coexist with historical ones |
| `is_active` | boolean | NOT NULL, default TRUE | False disables a factor without deleting it; useful if a source publishes a correction |

**Unique constraint:** `(activity_type, unit, valid_from)` — one factor per activity+unit per year.

**Why factors are not versioned on NormalizedEmission:** The factor FK on `NormalizedEmission` is a point-in-time snapshot — once a row is approved the FK cannot change. If DEFRA revises a factor, existing approved rows retain their original factor; only new ingestions pick up the update.

---

### `emissions_normalizedemission`

The computed emission record for one raw row. Created by the normalisation pipeline immediately after validation, before any analyst review.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | UUID | PK | |
| `tenant_id` | UUID | FK → `tenants_tenant`, CASCADE | |
| `raw_row_id` | UUID | FK → `ingestion_rawrow`, OneToOne, PROTECT | PROTECT: deleting a raw row must not silently remove the computed emission. The OneToOne enforces that exactly one emission exists per row |
| `batch_id` | UUID | FK → `ingestion_uploadbatch`, PROTECT | Denormalised from `raw_row.batch` for the scope-breakdown aggregation query: `GROUP BY tenant, batch__source_type` |
| `emission_factor_id` | integer | FK → `emissions_emissionfactor`, PROTECT | Records which specific factor version was used at normalisation time |
| `scope` | smallint | NOT NULL | Copied from the emission factor at normalisation time; denormalised for direct `filter(scope=1)` queries without a join |
| `activity_type` | varchar(60) | NOT NULL | Copied from the emission factor |
| `period_start` | date | NOT NULL | Start of the measurement period (document date for SAP; billing start for utility; travel date for travel) |
| `period_end` | date | NOT NULL | End of the measurement period |
| `quantity_raw` | decimal(15,4) | NOT NULL | Original quantity as parsed from the source, in the original unit |
| `unit_raw` | varchar(30) | NOT NULL | Original unit string (e.g. `L`, `Liter`, `MWH`) |
| `quantity_normalized` | decimal(15,4) | NOT NULL | Quantity after unit conversion to the canonical unit for this activity |
| `unit_normalized` | varchar(30) | NOT NULL | Canonical unit (e.g. `litre`, `kWh`, `km`, `room_night`) |
| `kg_co2e` | decimal(15,6) | NOT NULL | `quantity_normalized × emission_factor.kg_co2e_per_unit` |
| `location` | varchar(200) | nullable | Derived context: SAP → `plant:<code>`; Utility → site reference or supplier; Travel → route string |
| `cost_center` | varchar(100) | nullable | Carried through from the source file where present |
| `source_label` | varchar(200) | NOT NULL | Human-readable one-line description for the review UI (e.g. `SAP plant 1000 — Diesel EN590`) |
| `is_edited` | boolean | NOT NULL, default FALSE | Set to TRUE if an admin manually corrects `quantity_normalized` or `kg_co2e` after normalisation. Not currently exposed as an API endpoint; reserved for future use |
| `created_at` | timestamptz | NOT NULL, auto | |
| `updated_at` | timestamptz | NOT NULL, auto | |

**Indexes:** `(tenant, scope)` for scope-level breakdowns; `(tenant, period_start, period_end)` for date-range reports; `(tenant, activity_type)` for activity-level filtering; `(tenant, batch)` for per-upload views.

---

### `reviews_reviewdecision`

The analyst gate. One record per `NormalizedEmission`, created by the normalisation pipeline with `status=PENDING`. An analyst then approves or rejects it.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | UUID | PK | |
| `tenant_id` | UUID | FK → `tenants_tenant`, CASCADE | |
| `emission_id` | UUID | FK → `emissions_normalizedemission`, OneToOne, CASCADE | OneToOne — every emission has exactly one review decision |
| `status` | varchar(20) | NOT NULL, default `PENDING` | `PENDING` → `APPROVED` or `REJECTED` |
| `analyst_id` | UUID | FK → `users_tenantuser`, SET_NULL, nullable | SET_NULL so that deleting a user account does not lose the review history; the decision record and its audit log entries are preserved |
| `analyst_note` | text | nullable | Required on rejection (enforced in `review_service.py`, not at the DB layer). Optional on approval |
| `reviewed_at` | timestamptz | nullable | Set when status transitions out of PENDING |
| `is_locked` | boolean | NOT NULL, default FALSE | Set to TRUE on APPROVED, never on REJECTED. A locked row cannot be approved or rejected again |
| `created_at` | timestamptz | NOT NULL, auto | |

**Locking asymmetry:** Approved rows are locked (`is_locked=True`) because an approved emission is a statement of fact that has entered (or will enter) an external audit report. Rejected rows are intentionally NOT locked so that the source system can correct the underlying data and re-upload it. A corrected re-upload produces a new `RawRow`, a new `NormalizedEmission`, and a new `ReviewDecision`; the old rejected chain remains in the database as a historical record.

**Indexes:** `(tenant, status)` for the review queue; `(tenant, analyst)` for per-analyst reporting; `(tenant, is_locked)` for locked-row counts.

---

### `audit_auditlog`

Append-only event log. No application code deletes or updates audit records.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | UUID | PK | |
| `tenant_id` | UUID | FK → `tenants_tenant`, CASCADE | |
| `actor_id` | UUID | FK → `users_tenantuser`, SET_NULL, nullable | NULL for system-generated events (ingestion pipeline runs without a user context at the row level) |
| `action` | varchar(40) | NOT NULL, choices | `BATCH_INGESTED`, `ROW_VALIDATED`, `ROW_FLAGGED`, `ROW_NORMALIZED`, `ROW_APPROVED`, `ROW_REJECTED`, `NOTE_EDITED`, `ROW_UNLOCKED` |
| `content_type_id` | integer | FK → `django_content_type`, CASCADE | Django's `ContentType` framework FK — identifies the model class of the affected object |
| `object_id` | UUID | NOT NULL | PK of the affected object. Together with `content_type`, forms a generic FK that can point to any model |
| `content_object` | (virtual) | GenericForeignKey | Python accessor; not a database column |
| `object_repr` | varchar(300) | NOT NULL | String snapshot of the object at event time (e.g. `UploadBatch a1b2c3… (SAP_FUEL, 22 rows)`). Preserved even if the object is later deleted |
| `before_state` | JSONB | nullable | JSON snapshot of the relevant fields before the action. NULL for creation events |
| `after_state` | JSONB | nullable | JSON snapshot after the action. Contains the full new state, not just the diff, so it can be read in isolation |
| `timestamp` | timestamptz | NOT NULL, auto | |
| `ip_address` | inet | nullable | Captured from `request.META["REMOTE_ADDR"]` for user-initiated events; NULL for pipeline events |

**Why a generic FK instead of separate FKs per model:** The audit table records events across `UploadBatch`, `RawRow`, `NormalizedEmission`, and `ReviewDecision`. A union of nullable FKs would leave most columns NULL most of the time and would require a schema change to add a new auditable model. Django's ContentType generic FK adds one `JOIN` to resolve the object but keeps the schema stable.

**Indexes:** `(tenant, -timestamp)` for the chronological API response; `(content_type, object_id)` for per-object history lookups; `(tenant, actor)` for per-analyst reporting; `(tenant, action)` for action-type filtering.

---

## Cross-cutting design decisions

### UUID primary keys everywhere (except EmissionFactor)

All user-facing IDs are UUIDs generated at object creation time. This means:

- The frontend receives the batch ID in the upload response and can navigate directly to `/ingestion/batches/<uuid>/` without waiting for a database round-trip to confirm the sequence number.
- IDs are safe to expose in URLs — an integer sequence would let any authenticated user enumerate all batches by incrementing.
- UUIDs are globally unique so a row can be unambiguously identified in log files, support tickets, and external audit reports without a table qualifier.

`EmissionFactor` uses an integer PK because it is an internal reference table, never exposed as a URL parameter, and small enough that the UUID overhead is not worth the standardisation benefit.

### Tenant FK on every table

All tables except `Tenant` and `TenantUser` carry a direct `tenant_id` FK. This is intentional denormalisation. The alternative — filtering through a chain of JOINs back to the batch — would make every query more complex and every index less selective. The tenant column is always the leading field in every composite index, making it the primary partition key.

`TenantQuerySetMixin` enforces `filter(tenant=request.tenant)` on every `ListAPIView` and `RetrieveAPIView`, so no view can accidentally return cross-tenant data.

### No soft delete

None of the tables have an `is_deleted` flag. Deletions are rare and out of scope for this version. The append-only audit log captures all meaningful state transitions; if a row or batch needs to be "removed" the correct action is to reject it via `ReviewDecision`, not to delete it.

### JSONB for raw_data and audit snapshots

`raw_data` stores the original CSV row as-received. JSONB was chosen over plain `text` because:

1. It validates JSON at write time, preventing corrupt data.
2. It enables key-level queries from psql during debugging (`raw_data->>'MENGE'`).
3. It is rendered correctly by DRF serializers without manual `json.loads()`.

`before_state`/`after_state` on `AuditLog` use the same reasoning.

### Decimal precision

`kg_co2e_per_unit` uses `decimal(12,8)` — 8 decimal places — because rail emission factors are as low as 0.03549 kg CO₂e/km and rounding at fewer places would introduce a systematic bias across thousands of journeys. `kg_co2e` on the emission record uses `decimal(15,6)`, which is sufficient for large fleets (up to 999,999,999 tonnes CO₂e) while preserving sub-gram resolution.

### Immutability of approved rows

`is_locked=True` on `ReviewDecision` is the only hard lock in the system. Once an emission is approved:

- `review_service.approve()` refuses to re-process it (`raise ValueError("Row is already locked.")`).
- The normalisation pipeline never overwrites an existing `NormalizedEmission` — it only creates new ones for new `RawRow` records.
- The emission factor FK is frozen at its value at normalisation time.

This means the approved dataset is stable regardless of what happens to the `EmissionFactor` table in the future.
