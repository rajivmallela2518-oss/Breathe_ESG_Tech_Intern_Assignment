import csv
import io
import math
from datetime import datetime
from .base_parser import BaseParser


DATE_FORMATS = [
    "%d/%m/%Y",   # 03/01/2024 — Concur UK default
    "%m/%d/%Y",   # 01/03/2024 — Concur US default
    "%Y-%m-%d",   # 2024-01-03 — ISO
    "%d.%m.%Y",   # 03.01.2024 — German Concur instances
]

TRAVEL_COLUMN_MAP = {
    "Report_ID":         "report_id",
    "Employee_ID":       "employee_id",
    "Employee_Name":     "employee_name",
    "Department":        "department",
    "Cost_Center":       "cost_center",
    "Expense_Type":      "expense_type",
    "Transaction_Date":  "transaction_date",
    "Merchant_Name":     "merchant_name",
    "Origin_City":       "origin_city",
    "Origin_Country":    "origin_country",
    "Destination_City":  "destination_city",
    "Destination_Country": "destination_country",
    "Origin_IATA":       "origin_iata",
    "Destination_IATA":  "destination_iata",
    "Distance_km":       "distance_km",
    "Travel_Class":      "travel_class",
    "Hotel_Nights":      "hotel_nights",
    "Amount_Local":      "amount_local",
    "Currency":          "currency",
    "Notes":             "notes",
}

# Expense type string → canonical activity type.
# Concur uses free-text expense types; this maps the common variants.
EXPENSE_TYPE_MAP = {
    "air travel":       "FLIGHT",
    "airfare":          "FLIGHT",
    "flight":           "FLIGHT",
    "hotel":            "HOTEL_STAY",
    "accommodation":    "HOTEL_STAY",
    "lodging":          "HOTEL_STAY",
    "car rental":       "GROUND_TRANSPORT_RENTAL",
    "car hire":         "GROUND_TRANSPORT_RENTAL",
    "rental car":       "GROUND_TRANSPORT_RENTAL",
    "taxi":             "GROUND_TRANSPORT_TAXI",
    "rideshare":        "GROUND_TRANSPORT_TAXI",
    "uber":             "GROUND_TRANSPORT_TAXI",
    "ground transport": "GROUND_TRANSPORT_TAXI",
    "rail":             "GROUND_TRANSPORT_RAIL",
    "train":            "GROUND_TRANSPORT_RAIL",
    "eurostar":         "GROUND_TRANSPORT_RAIL",
}

# Great-circle distances (km) for common city-pair routes.
# In production this would be a database table or a geocoding API call.
# We use IATA code pairs — both directions stored.
# Source: great-circle calculator, rounded to nearest km.
IATA_DISTANCES = {
    ("LHR", "JFK"): 5540, ("JFK", "LHR"): 5540,
    ("LHR", "FRA"): 660,  ("FRA", "LHR"): 660,
    ("LHR", "SIN"): 10840,("SIN", "LHR"): 10840,
    ("LHR", "DXB"): 5490, ("DXB", "LHR"): 5490,
    ("BOM", "DEL"): 1148, ("DEL", "BOM"): 1148,
    ("BOM", "DXB"): 1930, ("DXB", "BOM"): 1930,
    ("BOM", "LHR"): 7190, ("LHR", "BOM"): 7190,
    ("HAM", "AMS"): 472,  ("AMS", "HAM"): 472,
    ("MUC", "JFK"): 6460, ("JFK", "MUC"): 6460,
    ("HKG", "LHR"): 9640, ("LHR", "HKG"): 9640,
    ("AMS", "LHR"): 370,  ("LHR", "AMS"): 370,
}

# Distance thresholds for flight classification (DEFRA 2023 definitions)
DOMESTIC_MAX_KM   = 500    # within-country short hop
SHORT_HAUL_MAX_KM = 3700   # up to 3,700 km = short-haul international


class TravelParser(BaseParser):
    """
    Parses Concur / Navan corporate travel CSV exports.

    Key complexities handled:
    - Flight distances often absent — resolved from IATA pair lookup table
    - Expense type is free text — mapped to canonical activity type
    - Hotel rows need night count, not distance
    - Ground transport often has no distance — handled as zero-emission in prototype
      (acknowledged in DECISIONS.md)
    - Travel class affects emission factor (business ×2, first ×3)
    - Duplicate expense report rows from Concur re-exports
    """

    def parse(self, file_obj):
        if isinstance(file_obj, (bytes, bytearray)):
            file_obj = io.BytesIO(file_obj)

        content = file_obj.read()
        if isinstance(content, bytes):
            content = content.decode("utf-8-sig", errors="replace")

        reader = csv.DictReader(io.StringIO(content))
        results = []

        for row_number, raw_row in enumerate(reader, start=1):
            raw_data = {k.strip(): (v.strip() if v else "") for k, v in raw_row.items() if k}
            canonical = self._map_to_canonical(raw_data)
            results.append({
                "row_number": row_number,
                "raw_data": raw_data,
                "canonical": canonical,
                "checksum": self.checksum(raw_data),
            })

        return results

    def _map_to_canonical(self, raw):
        canonical = {}
        for csv_col, canon_col in TRAVEL_COLUMN_MAP.items():
            canonical[canon_col] = raw.get(csv_col, "").strip()

        canonical["transaction_date"] = self._parse_date(canonical.get("transaction_date", ""))
        canonical["distance_km"]      = self._resolve_distance(canonical)
        canonical["hotel_nights"]     = self._parse_int(canonical.get("hotel_nights", ""))
        canonical["amount_local"]     = self._parse_float(canonical.get("amount_local", ""))
        canonical["activity_type"]    = self._classify_expense_type(canonical)
        canonical["travel_class"]     = canonical.get("travel_class", "Economy").strip() or "Economy"

        return canonical

    def _classify_expense_type(self, canonical):
        raw_type = canonical.get("expense_type", "").lower().strip()
        for keyword, activity in EXPENSE_TYPE_MAP.items():
            if keyword in raw_type:
                if activity == "FLIGHT":
                    return self._classify_flight(canonical)
                return activity
        return "UNKNOWN"

    def _classify_flight(self, canonical):
        distance = canonical.get("distance_km")
        if distance is None:
            return "FLIGHT_SHORT_HAUL"  # conservative default; flagged for review
        if distance <= DOMESTIC_MAX_KM:
            return "FLIGHT_DOMESTIC"
        if distance <= SHORT_HAUL_MAX_KM:
            return "FLIGHT_SHORT_HAUL"
        return "FLIGHT_LONG_HAUL"

    def _resolve_distance(self, canonical):
        """
        Use provided distance first. If absent, look up IATA pair table.
        If neither available, return None — validator will flag it.
        """
        provided = self._parse_float(canonical.get("distance_km", ""))
        if provided and provided > 0:
            return provided

        origin = canonical.get("origin_iata", "").upper().strip()
        dest   = canonical.get("destination_iata", "").upper().strip()
        if origin and dest:
            return IATA_DISTANCES.get((origin, dest))

        return None

    @staticmethod
    def _parse_date(value):
        if not value:
            return None
        for fmt in DATE_FORMATS:
            try:
                return datetime.strptime(value.strip(), fmt).date().isoformat()
            except ValueError:
                continue
        return None

    @staticmethod
    def _parse_float(value):
        if not value:
            return None
        try:
            return float(str(value).replace(",", ""))
        except ValueError:
            return None

    @staticmethod
    def _parse_int(value):
        if not value:
            return None
        try:
            return int(float(str(value).strip()))
        except (ValueError, TypeError):
            return None
