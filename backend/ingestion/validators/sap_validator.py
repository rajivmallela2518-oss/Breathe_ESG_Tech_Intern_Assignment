import statistics
from .base import BaseValidator, ValidationResult

# Units SAP is known to export for fuel/procurement.
# Anything outside this set gets flagged for analyst review.
KNOWN_UNITS = {
    "l", "liter", "litre", "L",        # liquid volume
    "kg", "KG",                         # mass (heating oil, LPG)
    "m3", "M3",                         # gas volume (natural gas)
    "gal", "GAL",                       # gallons (some US-facing plants)
    "t", "MT",                          # metric tonnes (bulk procurement)
    "kwh", "KWH", "kWh", "MWh", "MWH", # energy (rare in SAP fuel but exists)
}

# Fields that must be present and non-empty for a SAP fuel row to be usable.
MANDATORY_FIELDS = ["plant_code", "material_description", "posting_date", "quantity", "unit"]

# SAP plant code format: 2-letter country ISO + 2-digit number (e.g. UK01, DE02, IN01)
# Not enforced as ERROR — clients sometimes use custom codes — but flagged as WARNING.
import re
PLANT_CODE_PATTERN = re.compile(r"^[A-Z]{2}\d{2}$")


class SAPValidator(BaseValidator):
    """
    Validates canonical rows from the SAP parser.

    Rules (in order of severity):
      ERROR   — missing mandatory field, negative quantity, unparseable date
      WARNING — unknown unit, suspicious outlier quantity, invalid plant code format,
                duplicate row within this batch
      INFO    — missing optional field (vendor name, order number)
    """

    def check(self, canonical: dict, context: dict) -> list[ValidationResult]:
        results = []

        results.extend(self._check_mandatory_fields(canonical))
        results.extend(self._check_quantity(canonical, context))
        results.extend(self._check_date(canonical))
        results.extend(self._check_unit(canonical))
        results.extend(self._check_plant_code(canonical))
        results.extend(self._check_duplicate(canonical, context))
        results.extend(self._check_optional_fields(canonical))

        return results

    # ------------------------------------------------------------------ #
    # Individual rule methods                                              #
    # ------------------------------------------------------------------ #

    def _check_mandatory_fields(self, c):
        flags = []
        for field in MANDATORY_FIELDS:
            if not c.get(field):
                flags.append(ValidationResult(
                    flag_code="MISSING_MANDATORY_FIELD",
                    severity="ERROR",
                    field_name=field,
                    message=f"Mandatory field '{field}' is missing or empty.",
                ))
        return flags

    def _check_quantity(self, c, context):
        flags = []
        qty = c.get("quantity")
        if qty is None:
            return flags  # already caught by mandatory field check

        if qty < 0:
            flags.append(ValidationResult(
                flag_code="NEGATIVE_QUANTITY",
                severity="ERROR",
                field_name="quantity",
                message=f"Quantity is negative ({qty}). SAP reversal entries should be handled separately.",
            ))
            return flags  # no point running outlier check on negative

        # Outlier detection: flag if value is more than 3 standard deviations
        # from the batch mean. Requires at least 5 rows to compute meaningfully.
        batch_quantities = context.get("batch_quantities", [])
        if len(batch_quantities) >= 5:
            mean = statistics.mean(batch_quantities)
            stdev = statistics.stdev(batch_quantities)
            if stdev > 0 and abs(qty - mean) > 3 * stdev:
                flags.append(ValidationResult(
                    flag_code="IMPOSSIBLE_QUANTITY",
                    severity="WARNING",
                    field_name="quantity",
                    message=(
                        f"Quantity {qty} is {abs(qty - mean) / stdev:.1f} standard deviations "
                        f"from the batch mean ({mean:.1f}). Verify this is not a data entry error."
                    ),
                ))
        return flags

    def _check_date(self, c):
        flags = []
        for field in ("document_date", "posting_date"):
            value = c.get(field)
            if value is None and c.get(field, "sentinel") != "sentinel":
                # Field was present but _parse_date returned None — bad format
                flags.append(ValidationResult(
                    flag_code="INVALID_DATE",
                    severity="ERROR",
                    field_name=field,
                    message=f"'{field}' could not be parsed as a date. Raw value preserved in raw_data.",
                ))
        return flags

    def _check_unit(self, c):
        flags = []
        unit = c.get("unit", "")
        if unit and unit not in KNOWN_UNITS:
            flags.append(ValidationResult(
                flag_code="UNIT_UNRECOGNIZED",
                severity="WARNING",
                field_name="unit",
                message=(
                    f"Unit '{unit}' is not in the recognised SAP unit list. "
                    f"Normalization will be skipped until unit is resolved."
                ),
            ))
        return flags

    def _check_plant_code(self, c):
        flags = []
        code = c.get("plant_code", "")
        if code and not PLANT_CODE_PATTERN.match(code):
            flags.append(ValidationResult(
                flag_code="MISSING_OPTIONAL_FIELD",
                severity="INFO",
                field_name="plant_code",
                message=f"Plant code '{code}' does not match expected format XX99. May be a custom code.",
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
                    "This row is identical to a previously seen row in this batch. "
                    "SAP re-exports often include duplicate rows from prior periods."
                ),
            ))
        return flags

    def _check_optional_fields(self, c):
        flags = []
        if not c.get("vendor_name"):
            flags.append(ValidationResult(
                flag_code="MISSING_OPTIONAL_FIELD",
                severity="INFO",
                field_name="vendor_name",
                message="Vendor name is missing. Row can still be processed but provenance is reduced.",
            ))
        return flags
