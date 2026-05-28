# Sources

This document describes the research behind each data source format, the emission factor values used, and the methodological standards the calculations are based on. Every number in the `emission_factors` fixture can be traced to a citation here.

---

## Part 1 — Source format research

### SAP fuel and procurement (MB52 / ME2M flat file export)

**What the source represents.** SAP is the ERP system used by the majority of large manufacturing and logistics organisations to manage procurement. Fuel and energy consumption is typically captured via goods movements against cost centres. The two SAP standard reports that sustainability teams most commonly request for GHG data are:

- **MB52** — Warehouse stocks of materials, including current stock levels and historical movement data.
- **ME2M** — Purchase orders per material. Used when procurement teams extract fuel purchase records by material group.

Both reports can be exported as flat files from SAP GUI (transaction SE16N or via the SAP List Viewer "Export to spreadsheet" option) or via a custom ABAP extract requested from the SAP basis team.

**Column name choices.** SAP flat file exports output ABAP technical field names (MANDT, BUKRS, WERKS, MENGE, MEINS, BLDAT, BUDAT, MAKTX, LIFNR) rather than English display labels when the system language is German. UK SAP clients sometimes run in English but still export the technical names because the field mapping is defined in the ABAP report definition, not the UI. The sample file and parser use the technical names:

| Technical name | English meaning | Notes |
|----------------|-----------------|-------|
| `MANDT` | Client | 3-digit SAP client number (always 100 in demo systems) |
| `BUKRS` | Company code | e.g. `GB01` for UK entities |
| `WERKS` | Plant | The physical location where consumption occurs |
| `MATNR` | Material number | 18-digit zero-padded number; leading zeros stripped in parser |
| `MAKTX` | Material description | Free text; used for fuel type classification |
| `BWART` | Movement type | 201 = goods issue to cost centre; 261 = goods issue for order |
| `BLDAT` | Document date | Date the goods movement was physically recorded |
| `BUDAT` | Posting date | Accounting date; used as the emission period date |
| `MENGE` | Quantity | German locale: comma decimal separator |
| `MEINS` | Unit of measure | `L`, `l`, `Liter`, `KG`, `M3` depending on locale |
| `KOSTL` | Cost centre | Links consumption to business unit |
| `LIFNR` | Vendor number | Supplier account number in SAP |

**Movement type 201 / 261 filtering.** SAP records many types of stock movements in the same report. Only goods issues (outbound movements to cost centres or production orders) represent actual consumption. The BWART codes used in the sample data and filtered by the parser:

- `201`: Goods issue to cost centre — fuel consumed by an operation centre
- `261`: Goods issue for production order — fuel consumed in manufacturing

Movements such as `101` (goods receipt), `501` (receipt without purchase order), `201` reversals (`202`), and transfer postings (`311`) would appear in the same extract and must be excluded. Reference: SAP Help Portal, "Movement Types for Goods Movements" (help.sap.com/docs/SAP_ERP).

**German decimal format.** German SAP locales output `MENGE` as `6.100,000` (period as thousands separator, comma as decimal separator). This is the standard German numeric format (DIN 1333) and is reproduced in the sample file rows 6, 7, 16, 22. The parser's `_parse_decimal()` method handles both German and English formats by detecting which separator is used as decimal.

**SAP BOM encoding.** SAP flat file exports from older SAP versions (pre-S/4HANA) prepend a UTF-8 BOM (byte order mark: `\xef\xbb\xbf`) to the exported file. The parser uses `utf-8-sig` encoding to strip this transparently.

**Sample data design.** The 22-row sample file was constructed to exercise:
- UK, German, and Indian plants (UK01, UK02, UK03, DE01, DE02, IN01, IN02)
- Three date formats: `YYYYMMDD` (UK rows), `DD.MM.YYYY` (DE rows), `YYYY-MM-DD` (IN rows)
- German decimal notation (rows 6, 7, 16, 22)
- Duplicate rows from a re-export (rows 6 and 7 are identical)
- A statistical outlier (row 17: Manchester Depot petrol, 99,999 litres)
- A reversal entry (row 22: negative quantity `-150,000 l`)
- A missing `BLDAT` date (row 21: London HQ)
- Multiple fuel types: diesel EN590, petrol unleaded, natural gas, heating oil, LPG, furnace oil, biodiesel FAME B20, HSD (India), HVO blend

---

### Utility electricity (UK supplier portal CSV export)

**What the source represents.** UK electricity suppliers are required by Ofgem to provide half-hourly and monthly consumption data on request. Most medium and large business customers access this via a supplier online portal (British Gas Business Intelligence, EDF Energy Portal, Octopus Energy Business, E.ON UK Business, etc.) and download monthly invoice data as CSV. This is the standard route for multi-site estate managers collecting Scope 2 data.

**MPAN structure.** The Meter Point Administration Number (MPAN) is the unique identifier for an electricity supply point in Great Britain. It is a 21-digit number (S-number format) issued by the Distribution Network Operator (DNO). The standard core format for data exchange is 13 digits (the S number), but portals display it in various formats. Reference: Elexon BSC (Balancing and Settlement Code), "MPAN Format and Structure" (elexon.co.uk/bsc-and-panel/balancing-and-settlement-code/bsc-documents/).

German meters use different identifiers — the sample file includes `DE49112233445` for the Hamburg Werk, which follows the German DVGW/BNetzA metering point format.

**Column choices.** The column names in the utility sample file reflect the field names used by British Gas Business portal exports, which are the most common format seen in UK corporate energy management. EDF and Octopus portals use similar but not identical column names (e.g. "Consumption (kWh)" vs "Consumption_kWh"). The parser maps from the British Gas naming convention.

**Billing period format.** UK suppliers use DD/MM/YYYY for invoice and billing period dates. The sample data includes:
- Standard UK format: `01/01/2024`
- German format for E.ON Deutschland rows: `01.01.2024`
The parser tries both formats in order.

**Non-consumption rows.** UK electricity invoices routinely include non-consumption charge rows on the same statement: Climate Change Levy (CCL) standalone charges, standing charges, and Feed-in Tariff (FIT) export credits (negative kWh). These are filtered in `UtilityParser._is_non_consumption_row()` using the `Notes` field content.

**Estimated meter readings.** When a meter read cannot be obtained (locked premises, access dispute, network fault), the supplier issues an estimated reading marked `E` or `Estimated` in the `Reading_Type` field. The sample includes row 4 (Birmingham Lighting, `Estimated` in Reading_Type). This is flagged `INFO` — not blocking, because estimated reads are routine, but the analyst should be aware that the next actual read may trigger a true-up.

**Green tariff and REGOs.** The London HQ rows in the sample include supplier notes indicating green tariff and REGO attachments (`Green tariff - REGOs attached`, `Green tariff - Scope 2 market-based = 0`). The platform records these notes in `raw_data` but uses only the location-based emission factor for computation. This reflects the correct behaviour for a platform that does not yet implement market-based accounting (see TRADEOFFS.md §1).

**Sample data design.** The 20-row sample (plus filtered CCL row) exercises:
- UK (SITE-UK01, UK02, UK03), German (SITE-DE02), and Indian (SITE-IN01, SITE-IN02) sites
- UK and German date formats
- A duplicate invoice row (Manchester Depot, rows 6–7 with the same `Invoice_Number`)
- An MWh unit error (Mumbai Facility, row 17: `MWh` instead of `kWh`)
- An estimated reading (Birmingham Lighting, row 4)
- A solar FIT export row (negative consumption, filtered out)
- A CCL-only row (filtered out)
- A missing MPAN (Manchester sub-meter, row 20)
- A large outlier reading (Birmingham Plant March, 27,535 kWh vs ~7,000 typical)

---

### Corporate travel (Concur / SAP Concur expense report CSV)

**What the source represents.** SAP Concur is the most widely deployed corporate expense management platform for large organisations. Travel expense reports are submitted by employees and approved by line managers; the sustainability team then requests a CSV extract from the Concur Finance Administrator. The extract format is configurable, but the standard "Travel & Expense" extract includes the fields used in the sample file.

Navan (formerly TripActions) is the second most common platform for UK and European organisations and uses an identical column structure for the CSV export.

**Column choices.** The column names reflect the Concur standard extract field names. Notable fields:

- `Report_ID`: Concur expense report number — used as the grouping key for a single trip
- `Origin_IATA` / `Destination_IATA`: IATA airport codes — not always populated in Concur (depends on whether the booking was made through the corporate travel portal or directly); when absent, `Origin_City` and `Destination_City` are the fallback
- `Distance_km`: populated when the booking platform calculates distance, absent when booked direct or via a non-integrated provider
- `Travel_Class`: free text from the expense system — `Economy`, `Business`, `First`, `Premium Economy`; some submitters use abbreviations (`Eco`, `Biz`)
- `Hotel_Nights`: integer, present only for hotel expense lines
- `Amount_Local` / `Currency`: original transaction currency; not converted (no FX rates in the platform)

**IATA distance table.** When `Distance_km` is absent, the parser uses a hardcoded lookup table of great-circle distances for 12 common city-pair routes. Great-circle distances were calculated using the haversine formula and verified against:
- ICAO Doc 8126, "Aeronautical Information Services Manual" — reference for official great-circle distances
- OAG (Official Airline Guide) route database distances — used as a cross-check
- Google Maps "as the crow flies" distance tool — used as a sanity check

The 12 pairs in `IATA_DISTANCES` cover the routes present in the sample data: LHR–JFK, LHR–FRA, LHR–SIN, LHR–DXB, BOM–DEL, BOM–DXB, BOM–LHR, HAM–AMS, MUC–JFK, HKG–LHR, AMS–LHR. Both directions are stored separately with the same value (great-circle distance is symmetric).

**Sample data design.** The 26-row sample exercises:
- Domestic India flight (BOM–DEL, 1,148 km, distance provided)
- Short-haul business class (LHR–FRA, 660 km, distance from IATA table)
- Long-haul business class (LHR–SIN, 10,840 km, class multiplier ×2.0)
- First class long-haul (HKG–LHR, 9,640 km, class multiplier ×3.0)
- Eurostar rail (Amsterdam–London, 499 km, distance provided)
- Ground transport without distance (Uber London, zero emission with INFO flag)
- Car rental without distance (Hertz Singapore, zero emission with INFO flag)
- Missing employee ID (Anna Kowalski, INFO flag)
- Duplicate row (Sarah Mitchell LHR–JFK, row 24 = row 2)
- Hotel without amount (Thomas Braun New York, amount_local blank — row still normalises on hotel_nights)

---

## Part 2 — Emission factor sources

All factors are stored in `backend/emissions/fixtures/emission_factors.json` and loaded via `python manage.py loaddata emission_factors`.

### DEFRA 2023 Greenhouse Gas Reporting: Conversion Factors (v1.2)

**Full citation:** UK Department for Energy Security and Net Zero (DESNZ) and Department for Environment, Food and Rural Affairs (DEFRA). *Greenhouse gas reporting: conversion factors 2023*. Version 1.2. Published June 2023. Available at: assets.publishing.service.gov.uk/media/64d36afe1e10bf000ea8b88f/uk-greenhouse-gas-conversion-factors-2023-methodology-paper.pdf

This is the primary source for UK-based emission factors. DEFRA publishes updated factors annually, typically in June. The 2023 v1.2 factors are used throughout.

| Activity type | Unit | kg CO₂e / unit | DEFRA table |
|---------------|------|----------------|-------------|
| Diesel EN590 combustion | litre | 2.68800 | Table 1A (Fuel combustion — liquid fuels) |
| Petrol combustion | litre | 2.31200 | Table 1A |
| Natural gas combustion | m³ | 2.04300 | Table 1A (Natural gas, per m³ at standard conditions) |
| Heating oil combustion | kg | 3.17700 | Table 1A (Gas oil, per kg) |
| LPG combustion | kg | 2.94400 | Table 1A (Liquefied petroleum gas, per kg) |
| Biodiesel (FAME) combustion | litre | 0.19900 | Table 1A (Biodiesel (from used cooking oil), fossil fraction only) |
| Furnace oil combustion | kg | 3.17100 | Table 1A (Fuel oil, per kg) |
| UK grid electricity | kWh | 0.20705 | Table 12 (UK electricity: generation, transmission & distribution) |
| Flight domestic (≤500 km) | passenger-km | 0.25517 | Table 6 (Average passenger: domestic, with RF) |
| Flight short-haul (501–3,700 km) | passenger-km | 0.15396 | Table 6 (Average passenger: short-haul international, with RF) |
| Flight long-haul (>3,700 km) | passenger-km | 0.19085 | Table 6 (Average passenger: long-haul international, with RF) |
| Hotel stay | room-night | 31.47000 | Table 8 (Hotel stays — UK average) |
| Ground transport: taxi | km | 0.20369 | Table 5 (Average taxi) |
| Ground transport: car rental | km | 0.16844 | Table 5 (Average car — market average) |
| Ground transport: rail | km | 0.03549 | Table 5 (National rail) |

**Notes on the flight factor.** The DEFRA factors include a Radiative Forcing (RF) uplift of approximately 1.9×. RF accounts for the additional warming effect of water vapour contrails and cirrus cloud formation at altitude, which has a significant global warming impact beyond the direct CO₂ emitted. Some organisations report with and without RF; this platform uses the with-RF factor, which is the DEFRA recommended approach for corporate reporting.

**Travel class multipliers.** DEFRA 2023 Table 5 ("Passenger transport: air") provides multipliers for each travel class relative to economy. The factors applied in `normalization_service.py`:

| Class | Multiplier | Source |
|-------|-----------|--------|
| Economy | 1.00 | DEFRA 2023 Table 5, reference class |
| Premium Economy | 1.60 | DEFRA 2023 Table 5 |
| Business | 2.00 | DEFRA 2023 Table 5 |
| First | 3.00 | DEFRA 2023 Table 5 |

The multipliers reflect the greater seat pitch (and therefore floor-space allocation) of premium classes relative to economy, as well as the higher freight displacement.

**Flight distance classification thresholds.** DEFRA 2023 defines the three flight categories by passenger journey distance:

| Category | Distance range | DEFRA definition |
|----------|---------------|------------------|
| Domestic | ≤ 500 km | Flights within the UK (or within a single country boundary) |
| Short-haul international | 501–3,700 km | International flights within or close to continental range |
| Long-haul international | > 3,700 km | Transcontinental and intercontinental flights |

---

### UBA 2023 — German national grid electricity factor

**Full citation:** Umweltbundesamt (Federal Environment Agency, Germany). *Entwicklung der spezifischen Kohlendioxid-Emissionen des deutschen Strommix in den Jahren 1990–2022*. Published February 2023.

| Activity type | Unit | kg CO₂e / unit | Value |
|---------------|------|----------------|-------|
| German grid electricity | kWh | 0.36600 | UBA 2023 (market mix for Germany) |

Germany's grid factor is significantly higher than the UK's because of the ongoing coal phase-out period; the 2022 figure reflects a grid still partially reliant on lignite and hard coal.

---

### CEA 2022–23 — Indian national grid electricity factor

**Full citation:** Central Electricity Authority, Ministry of Power, Government of India. *CO₂ Baseline Database for the Indian Power Sector, Version 18.0*. Published 2023. Available at: cea.nic.in/cdm-co2-baseline-database.

| Activity type | Unit | kg CO₂e / unit | Value |
|---------------|------|----------------|-------|
| Indian grid electricity | kWh | 0.71600 | CEA 2022–23 (combined margin CO₂ baseline, national) |

India's grid factor is approximately 3.5× higher than the UK's, reflecting the large proportion of coal in the Indian generation mix. The CEA publishes separate values by region (EM, NR, NER, SR, WR grids); the national combined margin value is used here as the default.

---

### EEA 2023 — European Union average grid electricity factor

**Full citation:** European Environment Agency. *Greenhouse gas emission intensity of electricity generation in Europe*. Data published 2023. Available at: eea.europa.eu/data-and-maps/data/co2-intensity-of-electricity-generation.

| Activity type | Unit | kg CO₂e / unit | Value |
|---------------|------|----------------|-------|
| EU average grid electricity | kWh | 0.27600 | EEA 2023 EU-27 average |

Used as the fallback for utility rows where the site reference indicates a European country other than Germany, and for which no country-specific factor is loaded.

---

### IEA 2022 — Global average grid electricity factor

**Full citation:** International Energy Agency. *Greenhouse Gas Emissions from Energy: Overview*. IEA, Paris, 2022. Available at: iea.org/data-and-statistics/data-product/greenhouse-gas-emissions-from-energy.

| Activity type | Unit | kg CO₂e / unit | Value |
|---------------|------|----------------|-------|
| Unknown grid electricity | kWh | 0.23300 | IEA 2022 world average CO₂ intensity |

Applied when the grid zone cannot be determined from the site reference or supplier name. This value produces a WARNING flag (`GRID_ELECTRICITY_UNKNOWN`) in the review queue.

---

## Part 3 — Methodological references

### GHG Protocol Corporate Accounting and Reporting Standard

**Full citation:** World Resources Institute and World Business Council for Sustainable Development. *The Greenhouse Gas Protocol: A Corporate Accounting and Reporting Standard, Revised Edition*. 2004. Available at: ghgprotocol.org/corporate-standard.

The definitive standard for corporate GHG inventories. Establishes the three-scope framework:

- **Scope 1:** Direct GHG emissions from sources owned or controlled by the company (combustion of fuels in company-owned equipment and vehicles; fugitive emissions from refrigeration and industrial processes).
- **Scope 2:** Indirect emissions from the generation of purchased or acquired electricity, steam, heat, or cooling consumed by the company.
- **Scope 3:** All other indirect emissions that occur in a company's value chain, both upstream (Category 1–8) and downstream (Category 9–15).

The Scope 1 / Scope 2 / Scope 3 classification in `scope_classifier.py` and `ACTIVITY_SCOPE_MAP` follows this standard directly.

### GHG Protocol Scope 2 Guidance

**Full citation:** World Resources Institute. *GHG Protocol Scope 2 Guidance: An Amendment to the GHG Protocol Corporate Standard*. 2015. Available at: ghgprotocol.org/scope_2_guidance.

Establishes the requirement for dual reporting (location-based and market-based) for Scope 2 emissions. The platform implements location-based only; this document is the reference for the market-based gap described in TRADEOFFS.md §1.

### GHG Protocol Corporate Value Chain (Scope 3) Standard

**Full citation:** World Resources Institute and World Business Council for Sustainable Development. *Corporate Value Chain (Scope 3) Accounting and Reporting Standard*. 2011. Available at: ghgprotocol.org/standards/scope-3-standard.

Defines the 15 Scope 3 categories. Category 6 (Business Travel) is the one implemented. The category table in TRADEOFFS.md §2 was compiled from this standard.

### IPCC Fifth Assessment Report (AR5) — Global Warming Potentials

**Full citation:** Intergovernmental Panel on Climate Change. *Climate Change 2013: The Physical Science Basis. Contribution of Working Group I to the Fifth Assessment Report of the Intergovernmental Panel on Climate Change*. Cambridge University Press, 2013. Chapter 8, Table 8.7.

GWP values used to convert non-CO₂ greenhouse gases to CO₂-equivalent. The DEFRA 2023 conversion factors already embed AR5 100-year GWP values, so this standard is used implicitly throughout. Relevant if refrigerant emissions tracking is added in future (see TRADEOFFS.md §3).
