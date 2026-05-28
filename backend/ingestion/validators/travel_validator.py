from .base import BaseValidator, ValidationResult

KNOWN_ACTIVITY_TYPES = {
    "FLIGHT_DOMESTIC",
    "FLIGHT_SHORT_HAUL",
    "FLIGHT_LONG_HAUL",
    "HOTEL_STAY",
    "GROUND_TRANSPORT_RENTAL",
    "GROUND_TRANSPORT_TAXI",
    "GROUND_TRANSPORT_RAIL",
}

KNOWN_TRAVEL_CLASSES = {"economy", "business", "first", "premium economy", "n/a", ""}

# Hotel stays longer than this are flagged — likely two trips merged into one expense report
MAX_HOTEL_NIGHTS = 21

# Flights longer than this distance are implausible (Earth circumference / 2)
MAX_FLIGHT_KM = 20000


class TravelValidator(BaseValidator):
    """
    Validates canonical rows from the Concur/travel CSV parser.

    Key travel-specific concerns:
    - Missing distance for flights means we can't compute emissions accurately
    - Travel class materially affects the emission factor (business ×2, first ×3)
    - Hotel rows need a night count, not a distance
    - Ground transport without distance is flagged INFO — we can't compute but
      the row is not an error; production would use a cost-proxy method
    - Duplicate expense report rows are common from Concur re-exports
    """

    def check(self, canonical: dict, context: dict) -> list[ValidationResult]:
        results = []
        results.extend(self._check_mandatory_fields(canonical))
        results.extend(self._check_activity_type(canonical))
        results.extend(self._check_flight_distance(canonical))
        results.extend(self._check_hotel_nights(canonical))
        results.extend(self._check_ground_transport(canonical))
        results.extend(self._check_travel_class(canonical))
        results.extend(self._check_duplicate(canonical, context))
        results.extend(self._check_optional_fields(canonical))
        return results

    def _check_mandatory_fields(self, c):
        flags = []
        for field in ("expense_type", "transaction_date", "activity_type"):
            if not c.get(field):
                flags.append(ValidationResult(
                    flag_code="MISSING_MANDATORY_FIELD",
                    severity="ERROR",
                    field_name=field,
                    message=f"Mandatory field '{field}' is missing or could not be determined.",
                ))
        return flags

    def _check_activity_type(self, c):
        flags = []
        activity = c.get("activity_type", "")
        if activity == "UNKNOWN":
            flags.append(ValidationResult(
                flag_code="MISSING_MANDATORY_FIELD",
                severity="ERROR",
                field_name="expense_type",
                message=(
                    f"Expense type '{c.get('expense_type')}' could not be mapped to a known "
                    f"activity type. Row cannot be normalised until expense type is clarified."
                ),
            ))
        return flags

    def _check_flight_distance(self, c):
        flags = []
        if c.get("activity_type") not in ("FLIGHT_DOMESTIC", "FLIGHT_SHORT_HAUL", "FLIGHT_LONG_HAUL"):
            return flags

        distance = c.get("distance_km")

        if distance is None:
            origin = c.get("origin_iata", "")
            dest   = c.get("destination_iata", "")
            flags.append(ValidationResult(
                flag_code="MISSING_MANDATORY_FIELD",
                severity="WARNING",
                field_name="distance_km",
                message=(
                    f"Flight distance not provided and IATA pair ({origin}→{dest}) not found "
                    f"in lookup table. Emission calculation will use short-haul factor as a "
                    f"conservative default. Verify and update distance manually."
                ),
            ))
        elif distance > MAX_FLIGHT_KM:
            flags.append(ValidationResult(
                flag_code="IMPOSSIBLE_QUANTITY",
                severity="WARNING",
                field_name="distance_km",
                message=(
                    f"Flight distance {distance} km exceeds {MAX_FLIGHT_KM} km "
                    f"(half Earth circumference). Likely a data entry error."
                ),
            ))
        return flags

    def _check_hotel_nights(self, c):
        flags = []
        if c.get("activity_type") != "HOTEL_STAY":
            return flags

        nights = c.get("hotel_nights")

        if not nights or nights <= 0:
            flags.append(ValidationResult(
                flag_code="MISSING_MANDATORY_FIELD",
                severity="ERROR",
                field_name="hotel_nights",
                message=(
                    "Hotel stay row has no night count. Cannot compute room-night based "
                    "Scope 3 emission. Verify Hotel_Nights column is populated."
                ),
            ))
        elif nights > MAX_HOTEL_NIGHTS:
            flags.append(ValidationResult(
                flag_code="IMPOSSIBLE_QUANTITY",
                severity="WARNING",
                field_name="hotel_nights",
                message=(
                    f"Hotel stay of {nights} nights is unusually long (>{MAX_HOTEL_NIGHTS}). "
                    f"May be two trips merged in a single expense report line."
                ),
            ))
        return flags

    def _check_ground_transport(self, c):
        flags = []
        activity = c.get("activity_type", "")
        if activity not in ("GROUND_TRANSPORT_TAXI", "GROUND_TRANSPORT_RENTAL", "GROUND_TRANSPORT_RAIL"):
            return flags

        distance = c.get("distance_km")
        if not distance or distance <= 0:
            flags.append(ValidationResult(
                flag_code="MISSING_OPTIONAL_FIELD",
                severity="INFO",
                field_name="distance_km",
                message=(
                    f"Ground transport row has no distance. Scope 3 emission cannot be computed. "
                    f"In production a spend-based proxy (cost × emission intensity) would be used. "
                    f"Row will be approved with kg_co2e = 0 unless analyst adds a distance."
                ),
            ))
        return flags

    def _check_travel_class(self, c):
        flags = []
        activity = c.get("activity_type", "")
        if "FLIGHT" not in activity:
            return flags

        travel_class = c.get("travel_class", "").lower().strip()
        if travel_class not in KNOWN_TRAVEL_CLASSES:
            flags.append(ValidationResult(
                flag_code="UNIT_UNRECOGNIZED",
                severity="WARNING",
                field_name="travel_class",
                message=(
                    f"Travel class '{travel_class}' is not recognised. "
                    f"Expected: Economy, Premium Economy, Business, or First. "
                    f"Class multiplier will default to Economy (×1.0)."
                ),
            ))
        return flags

    def _check_duplicate(self, c, context):
        flags = []
        checksum = context.get("current_checksum")
        seen = context.get("seen_checksums", set())
        if checksum and checksum in seen:
            flags.append(ValidationResult(
                flag_code="DUPLICATE_ROW",
                severity="ERROR",
                field_name=None,
                message=(
                    "Identical row already seen in this batch. Concur re-exports often "
                    "include rows from prior reporting periods without deduplication."
                ),
            ))
        return flags

    def _check_optional_fields(self, c):
        flags = []
        if not c.get("employee_id"):
            flags.append(ValidationResult(
                flag_code="MISSING_OPTIONAL_FIELD",
                severity="INFO",
                field_name="employee_id",
                message=(
                    "Employee ID missing. Row can still be processed but cannot be "
                    "attributed to a specific individual for Scope 3 category 6 reporting."
                ),
            ))
        if not c.get("cost_center"):
            flags.append(ValidationResult(
                flag_code="MISSING_OPTIONAL_FIELD",
                severity="INFO",
                field_name="cost_center",
                message="Cost centre missing. Business travel cannot be attributed to a department.",
            ))
        return flags
