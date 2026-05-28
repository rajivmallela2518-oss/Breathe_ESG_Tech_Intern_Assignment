# Tradeoffs

This document describes what was deliberately left out, why, and what a production implementation would require to add it. It is intended to be honest rather than defensive: the gaps below are real limitations, not oversights.

The assignment asks for three data sources and a review workflow. Everything here is in addition to that scope.

---

## 1. Market-based Scope 2 accounting

**What is missing.** The platform computes Scope 2 emissions using the location-based method only — applying the average national grid emission factor (DEFRA/UBA/CEA) to the kWh billed. The GHG Protocol Scope 2 Guidance (2015) requires dual reporting for organisations that hold contractual instruments: both the location-based figure and the market-based figure, which may be zero for sites supplied entirely by renewable energy certificates (REGOs in the UK, Guarantees of Origin in the EU).

**What it would require.** Market-based accounting requires a third data source not present in any standard utility portal export: the renewable energy certificate registry. Each REGO or GO specifies a generation unit, a generation period, a kWh volume, and a cancellation date. Matching these certificates to the site's consumption requires:

- A separate ingestion pipeline for REGO/GO files (different source, different schema, different validation rules).
- A certificate matching engine that nets certificates against consumption for the same site and period.
- A residual mix factor for unmatched consumption (calculated by the energy regulator, updated annually).
- A new data model: `EnergyCertificate` linked to the site, and a `CertificateAllocation` linking certificates to `NormalizedEmission` records.

**Why it was excluded.** None of the three source systems described in the assignment (SAP, utility portal, Concur) provide certificate data. A utility portal CSV is a billing document, not a certificate registry extract. Adding market-based accounting without a real certificate data source would require either inventing a fourth data source or computing meaningless zeros. The location-based figure is always required under the GHG Protocol regardless of whether market-based is also reported; this prototype computes the mandatory baseline.

**Production gap.** Any organisation reporting to CDP, or holding RE100 or SBTi commitments, will need market-based Scope 2. The model schema supports extension: `EmissionFactor` has `is_active` and `valid_from/to`, so market-based factors could be loaded as a second factor set and selected by a new `accounting_method` field on `NormalizedEmission`.

---

## 2. GHG Protocol Scope 3 completeness

**What is missing.** The GHG Protocol Scope 3 Standard defines 15 categories. This platform covers exactly one: Category 6 (business travel). The other 14 are absent:

| Category | Description | Typical source |
|----------|-------------|----------------|
| 1 | Purchased goods and services | Spend-based or supplier-specific |
| 2 | Capital goods | Asset register, depreciation schedules |
| 3 | Fuel- and energy-related (not in Scope 1 or 2) | T&D losses, upstream extraction |
| 4 | Upstream transportation and distribution | Freight invoices, carrier data |
| 5 | Waste generated in operations | Waste contractor reports |
| 7 | Employee commuting | HR travel surveys |
| 8 | Upstream leased assets | Lease registry |
| 9–15 | Downstream categories | Customer usage, investments, franchises |

Category 3 (transmission and distribution losses) is particularly notable in its absence: the UK grid has ~8% T&D losses, meaning the true Scope 3 contribution from purchased electricity is approximately 8% of the Scope 2 figure. Omitting it is consistent with many corporate disclosures but is a methodological limitation.

**What it would require.** Each Scope 3 category has a different primary data source and calculation methodology. Category 1 (purchased goods) requires a spend-based approach using EEIO coefficients or supplier-specific Product Carbon Footprints — a fundamentally different calculation than the activity-based approach used here. Adding all 15 categories would multiply the surface area of the data model, parsers, and validation rules by roughly an order of magnitude.

**Why it was excluded.** The assignment specified three source systems that map to Scope 1 (fuel combustion), Scope 2 (electricity), and Scope 3 Category 6 (business travel). Extending to all 15 categories would require primary data sources the assignment does not provide. The architecture supports extension: new `source_type` values, new parsers, new validators, and new emission factor rows can be added without modifying the existing pipeline structure.

**Production gap.** A Scope 3 screening exercise (typically using EEIO spend-based coefficients as a first pass) is standard practice before scoping a more detailed Scope 3 programme. The review workflow and audit trail built here would apply directly to Category 1 data once a spend-based ingestion source was added.

---

## 3. Refrigerant and fugitive emissions (Scope 1 Category 1)

**What is missing.** Scope 1 includes not only stationary combustion (fuel burned in boilers, generators, and vehicles owned by the organisation) but also fugitive emissions: refrigerant leakage from HVAC and refrigeration equipment, SF₆ from switchgear, and process emissions from manufacturing or chemical operations. For many industrial organisations, refrigerant leakage can exceed combustion emissions in global warming potential because HFC refrigerants have GWP values in the hundreds to thousands.

**What it would require.** Refrigerant tracking requires a different source system entirely: a facilities management or maintenance system that records refrigerant top-ups and replacements, not an ERP or utility portal. The calculation is:

```
kg CO₂e = mass_of_refrigerant_added (kg) × GWP_of_refrigerant
```

GWP values come from the IPCC Fifth Assessment Report (AR5) or IPCC AR6 and vary from ~1 (CO₂) to 14,800 (HFC-23). The refrigerant type must be recorded at the equipment level; a single "refrigerant top-up" event without specifying the gas is uncomputable.

**Why it was excluded.** No refrigerant data source is specified in the assignment. SAP plant codes and material descriptions in the sample data are limited to liquid fuels and gas. Adding refrigerant tracking would require a fourth source type with a bespoke parser and a lookup table of 30+ refrigerant types and their GWP values.

**Production gap.** For real estate-heavy or cold-chain businesses, this is the most material omission in the Scope 1 calculation. The unit conversion framework is generic enough to accommodate mass-based refrigerant factors; the gap is in sourcing the input data.

---

## 4. API connectors — SAP OData, Concur REST, AMR portal

**What is missing.** All three source types are ingested via CSV file upload. In production, data would be pulled automatically on a schedule:

- **SAP:** SAP S/4HANA exposes the same procurement and material movement data via OData APIs (e.g. `/sap/opu/odata/sap/MM_PUR_POITEMS_BASIC_SRV`). A scheduled connector would eliminate the manual export-and-upload step.
- **Concur / Navan:** SAP Concur has a REST API that returns expense reports in JSON with the same fields as the CSV export. Navan provides webhooks for real-time expense submission events.
- **Utility AMR:** Advanced metering infrastructure (AMI) portals expose half-hourly consumption data via API (e.g. the DCC or directly from Octopus Energy's API). Half-hourly data is more precise than monthly billing and enables time-of-use carbon intensity tracking (grid carbon intensity varies by hour of day).

**What it would require.** Each connector requires OAuth2 credential management, rate limiting, pagination handling, incremental sync (not re-fetching already-ingested data), and error handling for API outages. The credential storage alone requires a secrets manager (AWS Secrets Manager, Vault) rather than environment variables, because each tenant would have different API credentials.

**Why it was excluded.** API connectors require external service credentials, OAuth flows, and network connectivity that are not available in an assignment context. The CSV upload path is the correct prototype approach: it exercises the entire pipeline (parse → validate → normalise → review) using real-format data without requiring live service connections. The parser base class (`BaseParser`) was designed with this extension in mind — an API connector would implement the same `parse()` interface returning the same `[{row_number, raw_data, canonical, checksum}]` structure.

**Production gap.** Manual CSV upload creates a data collection burden on sustainability teams (monthly downloads from three portals). Automated connectors would enable continuous ingestion, smaller batch sizes, and faster detection of anomalies.

---

## 5. Partial correction and batch amendment workflow

**What is missing.** When an analyst rejects a row, the current workflow expects the source system to be corrected and the entire file re-uploaded. There is no mechanism to:

- Correct a single row in the UI without a full re-upload.
- Mark specific rows in a batch as superseded by a later batch.
- Partially re-process a batch after a factor update.
- Merge corrections from two partial files into one batch.

**What it would require.** A correction workflow would need:

- An edit endpoint (`PATCH /emissions/<id>/`) that allows an analyst to override `quantity_normalized`, `unit_normalized`, or `kg_co2e` with a justification note, setting `is_edited=True` on the emission record and writing an audit log entry.
- A supersession model: a FK from a new `RawRow` to the row it supersedes, so the approved history shows both the original and the correction.
- A re-normalisation service: re-running the emission factor lookup and kg CO₂e calculation when a factor is updated, limited to rows that are not yet approved.
- UI for single-row editing in the review queue.

**Why it was excluded.** The correction workflow is complex to get right without creating audit integrity problems. Allowing arbitrary edits to approved emissions undermines the purpose of the approval gate. The `is_edited` flag is reserved on `NormalizedEmission` specifically because the data model supports it, but the service layer deliberately does not expose it to prevent accidental misuse. The analyst note on rejection is the correct signal back to the source system; re-upload produces a clean new chain with a full audit trail.

**Production gap.** Real sustainability teams deal with corrected invoices, late meter reads, and retrospective data. A partial correction workflow is necessary for production use; the current re-upload-everything approach becomes impractical for organisations with hundreds of meters.

---

## 6. Reporting and export layer

**What is missing.** The platform computes and reviews emissions but has no way to export them. A production system would need:

- **CSV / Excel export** of approved emissions filtered by scope, date range, and source.
- **PDF summary report** with total emissions by scope, period, and data source — the format typically submitted to board level or included in a sustainability report.
- **CDP / GRI submission format**: CDP's climate change questionnaire asks for C6.1 (Scope 1 total), C7.1 (Scope 2 location-based), C8.2a (Scope 3 by category) in a specific schema. Generating these from the approved dataset requires mapping the internal activity types to CDP categories.
- **Intensity metrics**: kg CO₂e per employee, per £ revenue, per m² of floor space. These require a denominator data source (HR headcount, financial data) that the platform does not have.
- **Year-over-year comparison**: emissions trends require the current year's approved data to be comparable to prior years', which requires consistent methodology documentation and factor versioning.

**Why it was excluded.** Reporting is a presentation layer built on top of a correct data foundation. The approved dataset in `NormalizedEmission` (filtered by `ReviewDecision.status = APPROVED`) contains everything needed to generate any of the above reports. The decision was to build the data pipeline correctly and treat export as a downstream concern. A read-only export endpoint can be added to the existing API without changing the data model.

**Production gap.** Without export, the platform cannot produce the deliverable that the sustainability team actually submits. The approved data exists in the database but cannot leave it without a developer writing a direct SQL query. This is the most visible functional gap for an end user.

---

## 7. Biogenic carbon separation

**What is missing.** Biodiesel and HVO (Hydrotreated Vegetable Oil) have very low fossil carbon emission factors (0.199 kg CO₂e/litre for biodiesel, compared to 2.688 for mineral diesel). However, combusting biofuel also releases biogenic CO₂ — CO₂ from carbon that was recently sequestered in plants. The GHG Protocol requires biogenic CO₂ to be reported separately from fossil CO₂, not added to the Scope 1 total.

The current platform uses the net fossil carbon factor (0.199 kg CO₂e/litre) for biodiesel, which is correct for the Scope 1 headline figure. But it does not separately track and report the biogenic CO₂ released (approximately 2.84 kg CO₂/litre for biodiesel combustion), which belongs in a separate disclosure line.

**What it would require.** A `biogenic_kg_co2` column on `NormalizedEmission`, populated for biofuel activity types using a second factor set. The emission factor table would need both `fossil_kg_co2e_per_unit` and `biogenic_kg_co2_per_unit`. The review UI would need to show both figures. CDP questionnaire C6.3 specifically asks for biogenic CO₂ emissions from combustion.

**Why it was excluded.** The separation matters for CDP disclosure but not for most internal carbon reduction reporting. The assignment sample data includes biodiesel rows but does not ask for biogenic/fossil split in the output. Adding biogenic tracking would require a schema migration, a UI change, and an additional factor column — material scope increase for a field that is optional in most corporate disclosures and required only at the CDP submission level.

**Production gap.** For organisations with significant biofuel consumption (logistics fleets switching to HVO, biomass boilers), omitting the biogenic figure would produce a non-compliant CDP submission. The fix is isolated: the `EmissionFactor` model needs one new column and the normalization service needs to populate it.
