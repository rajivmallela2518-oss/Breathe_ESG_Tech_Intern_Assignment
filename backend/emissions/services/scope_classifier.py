"""
Maps (source_type, activity_type) → GHG Protocol Scope.

Scope 1: Direct emissions from sources owned or controlled by the organisation
Scope 2: Indirect emissions from purchased electricity, steam, heat, or cooling
Scope 3: All other indirect emissions in the value chain

This mapping is the core ESG domain logic. Isolating it here means it can
be audited, updated for new source types, and unit-tested without touching
parsers or API code.
"""

# activity_type string → (scope, canonical_activity_type)
# canonical_activity_type must match a key in EmissionFactor.activity_type
ACTIVITY_SCOPE_MAP = {
    # ---------- Scope 1 — Fuel combustion (SAP source) ----------
    "DIESEL_COMBUSTION":          (1, "DIESEL_COMBUSTION"),
    "PETROL_COMBUSTION":          (1, "PETROL_COMBUSTION"),
    "NATURAL_GAS_COMBUSTION":     (1, "NATURAL_GAS_COMBUSTION"),
    "HEATING_OIL_COMBUSTION":     (1, "HEATING_OIL_COMBUSTION"),
    "LPG_COMBUSTION":             (1, "LPG_COMBUSTION"),
    "BIODIESEL_COMBUSTION":       (1, "BIODIESEL_COMBUSTION"),
    "FURNACE_OIL_COMBUSTION":     (1, "FURNACE_OIL_COMBUSTION"),

    # ---------- Scope 2 — Purchased electricity (Utility source) ----------
    "GRID_ELECTRICITY_UK":        (2, "GRID_ELECTRICITY_UK"),
    "GRID_ELECTRICITY_DE":        (2, "GRID_ELECTRICITY_DE"),
    "GRID_ELECTRICITY_IN":        (2, "GRID_ELECTRICITY_IN"),
    "GRID_ELECTRICITY_EU":        (2, "GRID_ELECTRICITY_EU"),
    "GRID_ELECTRICITY_UNKNOWN":   (2, "GRID_ELECTRICITY_UNKNOWN"),

    # ---------- Scope 3 — Corporate travel (Travel source) ----------
    "FLIGHT_DOMESTIC":            (3, "FLIGHT_DOMESTIC"),
    "FLIGHT_SHORT_HAUL":          (3, "FLIGHT_SHORT_HAUL"),
    "FLIGHT_LONG_HAUL":           (3, "FLIGHT_LONG_HAUL"),
    "HOTEL_STAY":                 (3, "HOTEL_STAY"),
    "GROUND_TRANSPORT_TAXI":      (3, "GROUND_TRANSPORT_TAXI"),
    "GROUND_TRANSPORT_RENTAL":    (3, "GROUND_TRANSPORT_RENTAL"),
    "GROUND_TRANSPORT_RAIL":      (3, "GROUND_TRANSPORT_RAIL"),
}

# Maps SAP material description keywords → activity_type
# Matching is case-insensitive prefix/substring, in priority order.
SAP_MATERIAL_TO_ACTIVITY = [
    ("biodiesel",         "BIODIESEL_COMBUSTION"),
    ("hvo",               "BIODIESEL_COMBUSTION"),   # Hydrotreated Vegetable Oil
    ("diesel",            "DIESEL_COMBUSTION"),
    ("dieselkraftstoff",  "DIESEL_COMBUSTION"),       # German
    ("hsd",               "DIESEL_COMBUSTION"),       # High Speed Diesel (India)
    ("petrol",            "PETROL_COMBUSTION"),
    ("unleaded",          "PETROL_COMBUSTION"),
    ("ms ",               "PETROL_COMBUSTION"),       # Motor Spirit (India)
    ("natural gas",       "NATURAL_GAS_COMBUSTION"),
    ("erdgas",            "NATURAL_GAS_COMBUSTION"),  # German
    ("mains gas",         "NATURAL_GAS_COMBUSTION"),
    ("heizöl",            "HEATING_OIL_COMBUSTION"),  # German heating oil
    ("heating oil",       "HEATING_OIL_COMBUSTION"),
    ("furnace oil",       "FURNACE_OIL_COMBUSTION"),
    ("lpg",               "LPG_COMBUSTION"),
    ("flüssiggas",        "LPG_COMBUSTION"),           # German LPG
]

# Maps site country code → grid electricity activity type
# Derived from plant_code prefix (UK → UK grid, DE → DE grid, IN → IN grid)
COUNTRY_TO_GRID = {
    "UK": "GRID_ELECTRICITY_UK",
    "GB": "GRID_ELECTRICITY_UK",
    "DE": "GRID_ELECTRICITY_DE",
    "IN": "GRID_ELECTRICITY_IN",
}


def classify_sap_row(canonical: dict) -> str:
    """
    Classify a SAP fuel row by inspecting the material description.
    Returns an activity_type string.
    """
    description = canonical.get("material_description", "").lower()
    for keyword, activity in SAP_MATERIAL_TO_ACTIVITY:
        if keyword in description:
            return activity
    return "DIESEL_COMBUSTION"  # safe fallback; flagged for analyst review


def classify_utility_row(canonical: dict) -> str:
    """
    Classify a utility electricity row.
    Uses site_reference or meter_mpan prefix to determine grid zone.
    """
    # site_reference like SITE-UK01 → UK, SITE-DE02 → DE, SITE-IN01 → IN
    site_ref = canonical.get("site_reference", "")
    for country_code, activity in COUNTRY_TO_GRID.items():
        if f"-{country_code}" in site_ref.upper():
            return activity

    # Fallback: try supplier name
    supplier = canonical.get("supplier", "").upper()
    if any(s in supplier for s in ("BRITISH GAS", "EDF", "OCTOPUS", "EON UK", "CENTRICA")):
        return "GRID_ELECTRICITY_UK"
    if any(s in supplier for s in ("E.ON ENERGIE", "VATTENFALL", "RWE", "MABANAFT")):
        return "GRID_ELECTRICITY_DE"
    if any(s in supplier for s in ("MSEDCL", "BSES", "TATA POWER", "ADANI")):
        return "GRID_ELECTRICITY_IN"

    return "GRID_ELECTRICITY_UNKNOWN"


def classify_travel_row(canonical: dict) -> str:
    """
    Travel rows carry their activity_type already resolved by TravelParser.
    This function just returns it, allowing the normalization service to call
    CLASSIFIER_MAP[source_type](canonical) uniformly across all three sources.
    """
    return canonical.get("activity_type", "FLIGHT_SHORT_HAUL")


def get_scope(activity_type: str) -> int:
    entry = ACTIVITY_SCOPE_MAP.get(activity_type)
    if entry:
        return entry[0]
    return 3  # unknown activities default to Scope 3 (most conservative)
