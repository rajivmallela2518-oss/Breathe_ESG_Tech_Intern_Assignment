# API Reference

Base URL: `https://<backend>.onrender.com/api/v1`  
All endpoints except `/auth/token/` and `/auth/token/refresh/` require a JWT bearer token.

```
Authorization: Bearer <access_token>
```

Every authenticated request is scoped to the tenant encoded in the token. Rows from other tenants are never returned.

---

## Authentication

### POST `/auth/token/`

Obtain access + refresh tokens. Embeds `tenant_slug`, `full_name`, and `role` as custom JWT claims so the frontend never needs a separate `/me` endpoint.

**Request**

```json
{
  "username": "analyst@acmecorp.com",
  "password": "s3cr3t"
}
```

**Response 200**

```json
{
  "access": "eyJ...",
  "refresh": "eyJ..."
}
```

The decoded `access` payload includes:

```json
{
  "user_id": "d4e7...",
  "tenant_slug": "acmecorp",
  "full_name": "Priya Sharma",
  "role": "ANALYST",
  "exp": 1748000000
}
```

**Errors**

| Code | Body |
|------|------|
| 401  | `{"detail": "No active account found..."}` |

---

### POST `/auth/token/refresh/`

Exchange a valid refresh token for a new access token (silent re-auth).

**Request**

```json
{ "refresh": "eyJ..." }
```

**Response 200**

```json
{ "access": "eyJ..." }
```

**Errors**

| Code | Body |
|------|------|
| 401  | `{"detail": "Token is invalid or expired"}` |

---

## Ingestion

### POST `/ingestion/upload/`

Upload a raw data file. Runs the full parse → validate → normalize pipeline synchronously. Returns immediately with row counts; the resulting rows are queryable via `/ingestion/batches/<id>/rows/` and appear in the review queue.

**Content-Type:** `multipart/form-data`

**Form fields**

| Field | Type | Required | Values |
|-------|------|----------|--------|
| `file` | File | Yes | `.csv` |
| `source_type` | String | Yes | `SAP_FUEL`, `UTILITY_ELECTRICITY`, `CORPORATE_TRAVEL` |

**Response 201**

```json
{
  "batch_id":    "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "total_rows":  22,
  "valid_rows":  17,
  "flagged_rows": 4,
  "failed_rows":  1,
  "status":      "COMPLETE"
}
```

`flagged_rows` are rows with at least one ERROR or WARNING flag — they are stored and normalised but will appear in the review queue with flags attached. `failed_rows` could not be parsed or normalised and are excluded from the review queue.

**Errors**

| Code | Body |
|------|------|
| 400  | `{"detail": "No file provided."}` |
| 400  | `{"detail": "source_type must be one of [...]"}` |
| 422  | `{"detail": "<parser or service error message>"}` |

---

### GET `/ingestion/batches/`

List all upload batches for the tenant, newest first.

**Response 200**

```json
[
  {
    "id":                "a1b2c3d4-...",
    "source_type":       "SAP_FUEL",
    "original_filename": "sap_fuel_procurement.csv",
    "status":            "COMPLETE",
    "total_rows":        22,
    "valid_rows":        17,
    "flagged_rows":       4,
    "failed_rows":        1,
    "uploaded_by_name":  "Priya Sharma",
    "created_at":        "2025-11-01T09:14:22Z",
    "completed_at":      "2025-11-01T09:14:24Z",
    "error_message":     null
  }
]
```

---

### GET `/ingestion/batches/<id>/`

Retrieve a single batch.

**Response 200** — same shape as the list item above.

**Errors**

| Code | Body |
|------|------|
| 404  | `{"detail": "Not found."}` |

---

### GET `/ingestion/batches/<id>/rows/`

All raw rows for a batch with their validation flags embedded. Used by the upload results page.

**Query params**

| Param | Values | Default |
|-------|--------|---------|
| `status` | `PENDING`, `VALID`, `FLAGGED`, `FAILED` | all |

**Response 200**

```json
[
  {
    "id":         "b9c0d1e2-...",
    "row_number": 3,
    "source_type": "SAP_FUEL",
    "status":     "FLAGGED",
    "raw_data": {
      "WERKS": "1000",
      "MENGE": "-500",
      "MEINS": "L",
      "BLDAT": "20241101",
      "MAKTX": "Diesel EN590"
    },
    "flags": [
      {
        "id":         "f1a2b3c4-...",
        "flag_code":  "NEGATIVE_QUANTITY",
        "severity":   "WARNING",
        "field_name": "MENGE",
        "message":    "Negative quantity may indicate a reversal entry."
      }
    ],
    "created_at": "2025-11-01T09:14:22Z"
  }
]
```

`raw_data` preserves the exact values as uploaded (pre-normalisation), useful for auditor review.

---

### GET `/ingestion/suspicious/`

All `FLAGGED` rows across the entire tenant, regardless of batch. Intended for the analyst "needs attention" view on the dashboard home page.

**Query params**

| Param | Values | Default |
|-------|--------|---------|
| `severity` | `ERROR`, `WARNING`, `INFO` | all |
| `source_type` | `SAP_FUEL`, `UTILITY_ELECTRICITY`, `CORPORATE_TRAVEL` | all |

**Response 200** — same shape as `/ingestion/batches/<id>/rows/` items.

Example with `?severity=ERROR`:

```json
[
  {
    "id":         "c3d4e5f6-...",
    "row_number": 7,
    "source_type": "CORPORATE_TRAVEL",
    "status":     "FLAGGED",
    "raw_data": {
      "employee_id": "",
      "expense_type": "Air Travel",
      "origin": "LHR",
      "destination": "---",
      "travel_class": "Business"
    },
    "flags": [
      {
        "id":         "a0b1c2d3-...",
        "flag_code":  "FLIGHT_NO_DISTANCE",
        "severity":   "ERROR",
        "field_name": "origin/destination",
        "message":    "Cannot resolve distance for LHR → ---. kg_co2e set to 0."
      }
    ],
    "created_at": "2025-11-01T10:32:05Z"
  }
]
```

---

### GET `/ingestion/summary/`

Aggregate counts for the analyst dashboard header cards.

**Response 200**

```json
{
  "total_rows": 68,
  "pending":    14,
  "approved":   49,
  "rejected":    3,
  "flagged":     6
}
```

`flagged` is the count of rows currently in `FLAGGED` status (these overlap with `pending` — a flagged row still has a PENDING review decision until an analyst acts on it).

---

## Emissions

### GET `/emissions/`

All normalised emission records for the tenant.

**Query params**

| Param | Values | Default |
|-------|--------|---------|
| `scope` | `1`, `2`, `3` | all |
| `source_type` | `SAP_FUEL`, `UTILITY_ELECTRICITY`, `CORPORATE_TRAVEL` | all |

**Response 200**

```json
[
  {
    "id":                  "e1f2a3b4-...",
    "scope":               1,
    "activity_type":       "diesel",
    "period_start":        "2024-11-01",
    "period_end":          "2024-11-01",
    "quantity_raw":        "6100.000",
    "unit_raw":            "L",
    "quantity_normalized": "6100.0000",
    "unit_normalized":     "litre",
    "kg_co2e":             "16396.800000",
    "location":            "plant:1000",
    "cost_center":         null,
    "source_label":        "SAP plant 1000 — Diesel EN590",
    "source_type":         "SAP_FUEL",
    "is_edited":           false,
    "emission_factor": {
      "id":              "f9e8d7c6-...",
      "activity_type":   "diesel",
      "scope":           1,
      "unit":            "litre",
      "kg_co2e_per_unit": "2.68800000",
      "source_reference": "DEFRA 2023 Table 1A",
      "valid_from":      "2023-01-01"
    },
    "review_status":  "APPROVED",
    "analyst_note":   null,
    "is_locked":      true,
    "created_at":     "2025-11-01T09:14:24Z",
    "updated_at":     "2025-11-01T11:02:17Z"
  }
]
```

---

### GET `/emissions/<id>/`

Single normalised emission record. Same shape as the list item.

**Errors**

| Code | Body |
|------|------|
| 404  | `{"detail": "Not found."}` |

---

### GET `/emissions/scope-breakdown/`

Totals grouped by GHG scope and source type. Powers the dashboard summary chart.

**Query params**

| Param | Values | Default |
|-------|--------|---------|
| `approved_only` | `true`, `false` | `false` |

**Response 200**

```json
[
  {
    "scope":               1,
    "batch__source_type":  "SAP_FUEL",
    "total_kg_co2e":       "52814.400000",
    "row_count":           17
  },
  {
    "scope":               2,
    "batch__source_type":  "UTILITY_ELECTRICITY",
    "total_kg_co2e":       "18639.450000",
    "row_count":           14
  },
  {
    "scope":               3,
    "batch__source_type":  "CORPORATE_TRAVEL",
    "total_kg_co2e":        "9427.810000",
    "row_count":           21
  }
]
```

Use `?approved_only=true` when you need the number to be audit-defensible (excludes rows still pending or rejected).

---

## Reviews

### GET `/reviews/`

Paginated review queue. Each item is a flat join of the `ReviewDecision`, its `NormalizedEmission`, and that emission's validation flags.

**Query params**

| Param | Values | Default |
|-------|--------|---------|
| `status` | `PENDING`, `APPROVED`, `REJECTED` | `PENDING` |

**Response 200**

```json
[
  {
    "id":                  "r1a2b3c4-...",
    "emission_id":         "e1f2a3b4-...",
    "review_status":       "PENDING",
    "analyst_note":        null,
    "is_locked":           false,
    "reviewed_at":         null,
    "scope":               1,
    "activity_type":       "diesel",
    "period_start":        "2024-11-01",
    "period_end":          "2024-11-01",
    "quantity_normalized": "6100.0000",
    "unit_normalized":     "litre",
    "kg_co2e":             "16396.800000",
    "source_label":        "SAP plant 1000 — Diesel EN590",
    "source_type":         "SAP_FUEL",
    "location":            "plant:1000",
    "flags": [
      {
        "id":         "f1a2b3c4-...",
        "flag_code":  "NEGATIVE_QUANTITY",
        "severity":   "WARNING",
        "field_name": "MENGE",
        "message":    "Negative quantity may indicate a reversal entry."
      }
    ]
  }
]
```

Flagged rows appear at the top of the default `PENDING` queue because the frontend sorts by flag severity client-side.

---

### POST `/reviews/<id>/approve/`

Approve a pending review decision. Sets `status=APPROVED` and `is_locked=True` on the row — the row cannot be approved or rejected again after this call.

**Request body:** empty (no body needed)

**Response 200**

```json
{ "status": "APPROVED" }
```

**Errors**

| Code | Body |
|------|------|
| 400  | `{"detail": "Row is already locked."}` |
| 404  | `{"detail": "Not found."}` |

---

### POST `/reviews/<id>/reject/`

Reject a pending review decision. Requires a non-empty analyst note (minimum 5 characters). Sets `status=REJECTED` but does **not** lock the row, allowing corrections and re-upload.

**Request body**

```json
{ "note": "Quantity appears to be a system reversal — confirm with SAP team before next upload." }
```

**Response 200**

```json
{ "status": "REJECTED" }
```

**Errors**

| Code | Body |
|------|------|
| 400  | `{"note": ["This field may not be blank."]}` |
| 400  | `{"detail": "Row is already locked."}` |
| 404  | `{"detail": "Not found."}` |

---

## Audit

### GET `/audit/`

Chronological, append-only audit trail for the tenant. No write endpoint exists — records are created by backend services only.

**Response 200**

```json
[
  {
    "id":          "aa1bb2cc-...",
    "actor":       "analyst@acmecorp.com",
    "action":      "ROW_APPROVED",
    "object_repr": "NormalizedEmission a1b2c3...",
    "before_state": {
      "review_status": "PENDING",
      "is_locked":     false
    },
    "after_state": {
      "review_status": "APPROVED",
      "is_locked":     true
    },
    "ip_address":  "196.168.1.42",
    "timestamp":   "2025-11-01T11:02:17Z"
  },
  {
    "id":          "bb2cc3dd-...",
    "actor":       null,
    "action":      "BATCH_INGESTED",
    "object_repr": "UploadBatch a1b2c3d4 (SAP_FUEL, 22 rows)",
    "before_state": null,
    "after_state": {
      "total_rows":   22,
      "valid_rows":   17,
      "flagged_rows":  4,
      "failed_rows":   1
    },
    "ip_address":  "196.168.1.42",
    "timestamp":   "2025-11-01T09:14:24Z"
  }
]
```

`actor` is `null` for system-generated events (ingestion pipeline). `before_state` and `after_state` are JSONB snapshots of the affected object.

---

## Error shape

All error responses follow the same envelope:

```json
{ "detail": "Human-readable description of the error." }
```

Validation errors (400 from serializers) use field-keyed lists:

```json
{
  "note": ["This field may not be blank."],
  "source_type": ["Value 'UNKNOWN' is not a valid choice."]
}
```

## Flag codes reference

| Code | Severity | Source | Meaning |
|------|----------|--------|---------|
| `MISSING_MANDATORY_FIELD` | ERROR | all | Required column is blank |
| `NEGATIVE_QUANTITY` | WARNING | SAP, Utility | Non-FIT negative consumption |
| `INVALID_DATE` | ERROR | SAP, Utility | Cannot parse date |
| `DUPLICATE_ROW` | ERROR | all | MD5 checksum matches prior row in this tenant |
| `STATISTICAL_OUTLIER` | WARNING | SAP | >3σ from batch mean (requires ≥5 rows) |
| `UNKNOWN_UNIT` | ERROR | SAP | Unit not in conversion table |
| `MISSING_VENDOR` | INFO | SAP | Vendor/supplier field blank |
| `REVERSED_DATES` | ERROR | Utility | Billing end before billing start |
| `BILLING_PERIOD_TOO_LONG` | WARNING | Utility | Period >95 days |
| `MWH_UNIT_RISK` | WARNING | Utility | Unit is MWh — verify not mistyped as kWh |
| `READING_DELTA_MISMATCH` | WARNING | Utility | Calculated consumption differs >1% from billed |
| `DUPLICATE_INVOICE` | ERROR | Utility | Invoice number seen in same batch |
| `ESTIMATED_READING` | INFO | Utility | Meter reading is estimated |
| `MISSING_MPAN` | WARNING | Utility | MPAN/meter ID blank |
| `UNMAPPABLE_EXPENSE_TYPE` | ERROR | Travel | Cannot classify expense as flight/hotel/ground |
| `HOTEL_NO_NIGHTS` | ERROR | Travel | Hotel row without nights field |
| `FLIGHT_NO_DISTANCE` | ERROR | Travel | Route not in IATA table and no distance provided |
| `UNREALISTIC_DISTANCE` | WARNING | Travel | Flight distance >20,000 km |
| `HOTEL_LONG_STAY` | WARNING | Travel | Hotel stay >21 nights |
| `UNKNOWN_TRAVEL_CLASS` | WARNING | Travel | Class not economy/premium economy/business/first |
| `MISSING_EMPLOYEE_ID` | INFO | Travel | Employee ID or cost centre blank |
| `GROUND_NO_DISTANCE` | INFO | Travel | Ground transport distance unknown — kg_co2e = 0 |
