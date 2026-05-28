# Decisions

This document records every significant ambiguity encountered while building the platform and the decision made to resolve it. Each entry follows the same pattern: the question that had to be answered, the choice made, what was rejected and why.

These were genuine design forks, not post-hoc rationalisation. The assignment left them deliberately open.

---

## 1. SAP source: What does a real SAP fuel export look like?

**The ambiguity.** The assignment says "SAP fuel/procurement data" but does not specify whether the export is a standard SAP report (MB52, ME2M, MB51), a custom ABAP extract, a BW query, or a third-party integration. Column names, delimiters, date formats, and decimal formats all depend on the SAP client language and the extracting user's locale.

**Decision.** Modelled the parser on the MB52 (material stock) / ME2M (purchase order) flat file export that sustainability teams most commonly receive from SAP basis teams when requesting GHG data. Specific choices:

- **Semicolon delimiter.** European SAP installations default to semicolons; UK and German clients both do this. A comma delimiter is used internally by SAP but is rare in human-exported files.
- **German column names alongside English.** Real SAP exports from German-language clients output `MENGE`, `MEINS`, `WERKS`, `BLDAT`, `BUDAT` — the ABAP field names, not English translations. The column map stores both so either client language works.
- **Movement type filtering.** Only movement types 201 (goods issue to cost centre) and 261 (goods issue for order) represent actual fuel consumption. Types 101 (goods receipt), 501 (receipt without PO), and reversal types (102, 202) appear in the same flat file and must be excluded. The decision: silently drop non-consumption movement types rather than flagging them, because they are expected and routine.
- **German decimal format.** `MENGE` is stored as `6.100,000` (period = thousands, comma = decimal) in German locales and `6100.000` in EN locales. Both are handled in `_parse_decimal()`. An ambiguous case like `6100` (no separator) is treated as standard.

**Rejected:** Using Python's `babel` or `locale` library to detect the decimal locale automatically. The detection heuristic for the ambiguous `6100` case is fragile and locale-dependent. An explicit two-pattern check is simpler and more predictable.

---

## 2. SAP source: How to classify fuel type from material description?

**The ambiguity.** SAP material descriptions are free text entered by procurement teams. There is no standard coding for "diesel" vs "biodiesel". The same material might be described as "Diesel EN590", "Dieselkraftstoff B7", "HSD (High Speed Diesel)", or "Gas Oil".

**Decision.** Priority-ordered keyword matching in `SAP_MATERIAL_TO_ACTIVITY`:

1. Check for `biodiesel` or `hvo` first — biodiesel has a significantly lower emission factor (0.199 kg/L vs 2.688 kg/L for diesel). Misclassifying biodiesel as diesel would massively overstate Scope 1.
2. Then check for `diesel`, `dieselkraftstoff`, `hsd`.
3. Then `petrol`, `unleaded`, `ms ` (Motor Spirit, common in India).
4. Then natural gas variants including the German `erdgas`.
5. Heating oil, LPG, furnace oil.
6. Fallback: `DIESEL_COMBUSTION` — the most common fuel in most corporate fleets.

The fallback is intentional rather than raising an error: an unclassified fuel row is better in the review queue as diesel than blocked as FAILED. The analyst can see it and correct it.

**Rejected:** A lookup table keyed on SAP material number (`MATNR`). Material numbers are client-specific and not portable across organisations. A keyword approach works across all tenants with no configuration.

---

## 3. Utility source: What to do with non-consumption rows in the same file?

**The ambiguity.** UK electricity portal exports intermix consumption rows with administrative charges: Climate Change Levy (CCL) rows, standing charge rows, Feed-in Tariff (FIT) export credits (negative consumption), and adjustment rows. Processing them would produce nonsensical emission records.

**Decision.** Filter non-consumption rows in the parser before rows are even stored, using `_is_non_consumption_row()`. These rows do not become `RawRow` records at all — they are silently dropped with no `ValidationFlag`. This keeps the database clean and prevents the review queue from filling with irrelevant entries.

Specifically excluded: rows where the `Notes` field contains `ccl charge only`, `standing charge`, `administration charge`, or `fit export`. A row with no `Consumption_kWh` and no meter readings is also dropped.

FIT export rows are an important edge case: they are negative consumption (the site is exporting power) and are not an emission. Silently dropping them is correct for a Scope 2 calculation. If the client also wants to report energy generation separately, that is a separate data model outside this assignment's scope.

**Rejected:** Storing FIT rows as FAILED with an explanation flag. This would fill the review queue with rows an analyst is not expected to act on, degrading signal-to-noise in the queue.

---

## 4. Utility source: What to do when the unit field says MWh instead of kWh?

**The ambiguity.** The unit converter knows how to convert MWh to kWh (×1000). It would be silent and technically correct to apply the conversion automatically. However, MWh in a field normally labelled kWh is almost always a data entry error — a 1 MWh billing row is plausible, but a 150 MWh row that should be 150 kWh is a 1000× error.

**Decision.** Flag it `WARNING` with the specific message "Unit is MWh — verify this is not a kWh data entry error. 1 MWh = 1000 kWh." rather than silently converting. The unit converter still performs the conversion so the row gets a `NormalizedEmission` and enters the review queue. The analyst must explicitly approve it.

**Rejected:** Treating it as an ERROR and blocking the row entirely. The unit may genuinely be MWh for large industrial sites. Blocking it would prevent those legitimate rows from being normalised.

---

## 5. Utility source: How to determine which national grid emission factor to use?

**The ambiguity.** A utility CSV contains electricity consumption from meters in multiple countries. The file has no country field. The correct factor for UK grid (0.207 kg/kWh) vs Indian grid (0.716 kg/kWh) varies by a factor of 3.5 — getting this wrong is a major emissions error.

**Decision.** Three-tier fallback in `classify_utility_row()`:

1. **Site reference prefix.** `SITE-UK01` → UK, `SITE-DE02` → DE, `SITE-IN01` → IN. This works if the client follows a consistent site reference naming convention, which is common in multi-site estate management.
2. **Supplier name keyword match.** British Gas, EDF, Octopus → UK. E.ON Energie, Vattenfall → DE. MSEDCL, BSES, Tata Power → IN.
3. **Fallback: `GRID_ELECTRICITY_UNKNOWN`** with a generic factor (0.233 kg/kWh, the IEA global average). This produces a row with a WARNING flag so the analyst knows the grid zone could not be determined.

**Rejected:** Using the MPAN number structure to determine the country. MPANs are a UK-specific format; non-UK meters use different identifiers. A MPAN-based lookup would break for DE and IN sites.

---

## 6. Travel source: What to do when flight distance is not provided?

**The ambiguity.** The Concur/Navan export may or may not include a `Distance_km` field. Many expense systems record only the route (LHR → JFK) and the ticket cost, not the distance. Without distance, a passenger-km emission factor cannot be applied.

**Decision.** Three-tier resolution in `TravelParser._resolve_distance()`:

1. Use the provided `Distance_km` if present and positive.
2. If absent, look up the IATA origin-destination pair in the hardcoded `IATA_DISTANCES` table (12 route pairs covering London, Frankfurt, Singapore, Dubai, Mumbai, Delhi, Hamburg, Amsterdam, Munich, Hong Kong).
3. If neither, return `None` — validator raises `FLIGHT_NO_DISTANCE` WARNING and the normalisation sets `kg_co2e = 0`.

A row with `kg_co2e = 0` is highly visible in the review queue. Zero is the right sentinel value: it does not silently overstate emissions (unlike using a default distance) and it cannot be mistaken for "this row has no emissions" because it appears with a WARNING flag.

**Rejected:** Calling a geocoding API (Google Maps Distance Matrix, ICAO, OAG) at ingestion time. This would make the pipeline dependent on an external service, add latency, require an API key, and introduce a network call inside a synchronous file upload. The IATA table covers the routes in the sample data.

---

## 7. Travel source: How to apply travel class to the emission factor?

**The ambiguity.** DEFRA 2023 publishes a single per-passenger-km factor for flights, not separate factors by class. The emission difference between economy and business is real (seat pitch, freight capacity share) and methodologically justified, but the implementation options vary.

**Decision.** Apply DEFRA 2023 Table 5 class multipliers on top of the base passenger-km factor in `normalize_batch()`:

| Class | Multiplier |
|-------|-----------|
| Economy | 1.0× |
| Premium Economy | 1.6× |
| Business | 2.0× |
| First | 3.0× |

The base `EmissionFactor` record stores the economy rate. The multiplier is applied in the normalisation service, not in the emission factor table. This means one factor record per flight category (domestic/short/long) rather than four per category.

**Rejected:** Storing four separate emission factors (economy, premium economy, business, first) per flight category. That would require 12 factor records instead of 3 for flights, and would make the factor table harder to update when DEFRA releases new figures.

---

## 8. Ground transport without distance: error, zero, or skip?

**The ambiguity.** Taxi, rental car, and ride-share rows rarely carry a distance field in corporate expense systems — only the amount. Without distance, a per-km emission factor cannot be applied.

**Decision.** Produce a `NormalizedEmission` with `kg_co2e = 0` and a `GROUND_NO_DISTANCE` INFO flag. The row enters the review queue as a zero-emission record that is visible to the analyst but does not require action.

The INFO severity means the row is `VALID` (not `FLAGGED`) and will not sort to the top of the pending queue. This is the correct analyst UX: ground transport without distance is common and expected; it should not clutter the queue with items that cannot be resolved without contacting the employee.

**Rejected:** Blocking the row as FAILED. An analyst cannot do anything with a FAILED row. A zero-emission row in the approved dataset is the honest representation: "we know this travel occurred, we cannot quantify it."

---

## 9. Outlier detection: what threshold and what minimum sample size?

**The ambiguity.** A statistical outlier threshold is a policy choice. >2σ catches more outliers but has more false positives (a genuine high-consumption month at a large facility). >3σ is stricter. A 95th-percentile cap ignores distribution shape.

**Decision.** >3σ from the batch mean, with a minimum of 5 rows in the batch before the check runs. Implementation in `validation_service.py` using `statistics.stdev()` on non-negative quantities.

- **3σ** rather than 2σ: in a normal distribution, 3σ captures 99.7% of legitimate values. SAP fuel batches are not perfectly normal (they include seasonal variation) but 3σ avoids flagging every large site's routine consumption.
- **5-row minimum**: `statistics.stdev()` raises on fewer than 2 items and is meaningless on fewer than 5. Below 5 rows there is no meaningful population to compare against.
- **Batch-level not cross-batch**: outlier detection is within the uploaded batch only. Cross-batch outlier detection would require storing rolling statistics and is not implemented.

**Rejected:** A fixed absolute threshold (e.g. ">10,000 litres is suspicious"). A fixed threshold is meaningless across organisations of different sizes. A relative threshold adapts to each batch automatically.

---

## 10. Duplicate detection: checksum algorithm and scope

**The ambiguity.** Row-level duplicates arise from two sources: (a) the same row appears twice in one file (copy-paste or system glitch), and (b) an entire file is re-uploaded in a subsequent batch. Both need to be caught.

**Decision.** Two-level approach:

1. **File-level:** SHA-256 hash of the raw file bytes stored on `UploadBatch.file_hash`. Not currently enforced as a uniqueness constraint (a re-upload may be intentional after a correction) but visible in the batch detail API.
2. **Row-level:** MD5 hex of `json.dumps(raw_data, sort_keys=True)` stored on `RawRow.checksum`. Cross-batch detection pre-fetches all existing checksums for the same `(tenant, source_type)` combination in one query before the validation loop. Within-batch detection uses an in-memory set.

**Why MD5:** MD5 is not cryptographically secure, but this is a business dedup signal, not a security control. MD5 is fast to compute per row, 32 characters (fits varchar(32)), and has negligible collision probability for the data volumes involved (billions of rows would be needed to make a collision likely). The full `raw_data` JSONB is stored so any collision can be investigated.

**What "duplicate" means here:** two rows with the same checksum should not both appear as approved emissions — that would double-count the activity. The first occurrence is processed; the duplicate is flagged `DUPLICATE_ROW` with ERROR severity so the analyst explicitly approves the re-upload if it was intentional.

---

## 11. Pipeline execution: synchronous vs asynchronous

**The ambiguity.** Parse → validate → normalise could run in a Celery task (background), returning a task ID immediately and polling for completion. Or it could run synchronously in the request, returning results when done.

**Decision.** Synchronous execution. The pipeline runs inside the `POST /ingestion/upload/` request handler. The response does not return until all rows are parsed, validated, and normalised.

**Rationale:** The largest sample files are ~26 rows. Even at 10,000 rows a synchronous pipeline on PostgreSQL completes in under two seconds on a Render Starter instance. The frontend receives the row counts in the upload response and can navigate to the review queue immediately. Adding Celery, a Redis broker, and a polling endpoint for a dataset this size would be significant infrastructure for no user-visible benefit.

**Rejected:** Celery + Redis. This would be the right choice for batches of 100,000+ rows or if the pipeline needed to call external services (geocoding, carbon accounting APIs). For this prototype, it is over-engineering.

---

## 12. Multi-tenancy: shared schema or separate schemas

**The ambiguity.** Multi-tenancy can be implemented as: (a) a `tenant_id` column on every table with row-level filtering (shared schema), (b) a separate PostgreSQL schema per tenant with a `search_path` switch, or (c) a separate database per tenant.

**Decision.** Shared schema with a `tenant_id` FK on every table, enforced by `TenantMiddleware` + `TenantQuerySetMixin`. The `tenant_slug` is embedded in the JWT so middleware can resolve the tenant without a DB lookup on every request.

**Rationale:** Separate-schema multi-tenancy requires dynamic `search_path` management, complicates migrations (they must run per tenant), and makes cross-tenant analytics queries (if ever needed by the platform operator) impossible. For a platform with many small tenants, the shared-schema approach is standard and maintainable.

The risk of data leakage between tenants is mitigated by the middleware: any request without a valid JWT containing a `tenant_slug` claim is rejected with 403 before reaching any view. The `TenantQuerySetMixin` adds `.filter(tenant=request.tenant)` on every queryset so even a bug in a view cannot return cross-tenant rows without explicitly bypassing the mixin.

---

## 13. Review decisions: why REJECTED rows are not locked

**The ambiguity.** When an analyst rejects a row, should the rejection itself be final (locked) or should the row be correctable?

**Decision.** REJECTED rows are not locked (`is_locked` remains False). Only APPROVED rows are locked.

**Rationale:** The purpose of a rejection is to send a data quality signal back to the source system so the record can be corrected. If rejections were locked, there would be no recovery path: a mis-rejected row would be permanently excluded from the approved dataset without any mechanism for an analyst to reverse their decision. The correct flow is:

1. Analyst rejects with a note (e.g. "Check with SAP team — this looks like a reversal").
2. The source system corrects the data.
3. The corrected file is re-uploaded. A new `RawRow`, `NormalizedEmission`, and `ReviewDecision` are created.
4. The original rejected chain remains in the database as history, visible in the audit log.

APPROVED rows are locked because an approval is a statement that the emission record is accurate and ready for external reporting. Changing it after the fact would undermine the audit trail.

---

## 14. Scope 2: location-based or market-based accounting?

**The ambiguity.** GHG Protocol Scope 2 guidance allows two methods: location-based (use the average grid emission factor for the country where the site is located) or market-based (use contractual instruments such as renewable energy certificates and supplier-specific rates). For organisations purchasing green electricity via PPAs or REGOs, the market-based figure is lower and often the one reported to CDP or in sustainability reports.

**Decision.** Location-based only. The grid factors from DEFRA 2023 / IEA are applied based on the country resolved from the site reference or supplier name.

**Rationale:** Market-based accounting requires per-supplier contractual instruments (REGOs, GOs, PPA declarations) that are not present in a standard utility portal CSV export. Implementing market-based would require a separate data source (the renewable certificate registry) and additional UI for linking certificates to sites. This is explicitly deferred in TRADEOFFS.md.

The location-based result is always computed and is the correct baseline. If a client needs market-based figures, the approved location-based dataset provides the denominator for the dual-reporting calculation.

---

## 15. Emission factor versioning: what happens when DEFRA updates figures?

**The ambiguity.** DEFRA releases updated conversion factors every year (usually in June). When new factors are loaded, should historical approved rows be recalculated, or should they retain the factor that was in effect when they were ingested?

**Decision.** Historical approved rows retain the original emission factor FK. New ingestions automatically pick up the latest active factor via `ORDER BY valid_from DESC LIMIT 1`. The `valid_from` / `valid_to` range on `EmissionFactor` supports coexistence of old and new factors.

**Rationale:** Re-calculating historical rows would silently change an approved, locked dataset. An auditor who verified the dataset against last year's factors would find the numbers had changed without any decision being made. The correct process is to note the factor revision in the annual report's methodology section and apply new factors to the current reporting year only. Locking approved rows to their original factor is the implementable version of that policy.
