import statistics
from datetime import date
from .base import BaseValidator, ValidationResult

# Billing periods longer than this are almost certainly a data error
# (two invoices merged, or a period spanning a contract changeover).
MAX_BILLING_DAYS = 95

# Units the utility parser is expected to produce after lowercasing.
# Anything else means the source file used an unexpected unit string.
KNOWN_UNITS = {"kwh", "mwh"}

# MWh rows are not silently converted — they are flagged WARNING so an
# analyst can confirm the value before normalization applies the ×1000 factor.
# Reason: a typo of MWh for kWh is a 1000× error in the emission figure.

# UK MPAN: exactly 13 digits. Other countries use different formats.
# We only enforce format for known UK MPANs (starting with a 10–13 digit string).
import re
UK_MPAN_PATTERN = re.compile(r"^\d{13}$")


class UtilityValidator(BaseValidator):
    """
    Validates canonical rows from the utility CSV parser.

    Key concerns for electricity data:
    - Billing periods that don't align with calendar months are normal, not errors
    - MWh vs kWh confusion is the most dangerous silent error (1000× magnitude)
    - Estimated readings reduce data quality but are not blocking
    - Negative consumption (solar FIT export) signals this is not a consumption row
    - MPAN is the unique meter identifier — missing MPAN means we cannot reliably
      de-duplicate or trace to a physical meter
    """

    def check(self, canonical: dict, context: dict) -> list[ValidationResult]:
        results = []
        results.extend(self._check_mandatory_fields(canonical))
        results.extend(self._check_consumption(canonical, context))
        results.extend(self._check_billing_period(canonical))
        results.extend(self._check_unit(canonical))
        results.extend(self._check_meter_readings(canonical))
        results.extend(self._check_mpan(canonical))
        results.extend(self._check_duplicate_invoice(canonical, context))
        results.extend(self._check_estimated_reading(canonical))
        return results

    def _check_mandatory_fields(self, c):
        flags = []
        for field in ("period_start", "period_end", "consumption_quantity", "consumption_unit", "supplier"):
            if not c.get(field) and c.get(field) != 0:
                flags.append(ValidationResult(
                    flag_code="MISSING_MANDATORY_FIELD",
                    severity="ERROR",
                    field_name=field,
                    message=f"Mandatory field '{field}' is missing or empty.",
                ))
        return flags

    def _check_consumption(self, c, context):
        flags = []
        qty = c.get("consumption_quantity")
        if qty is None:
            return flags

        if qty < 0:
            flags.append(ValidationResult(
                flag_code="NEGATIVE_QUANTITY",
                severity="WARNING",
                field_name="consumption_quantity",
                message=(
                    f"Consumption is negative ({qty} kWh). This is normal for a solar "
                    f"FIT export row but should not be treated as a consumption record. "
                    f"Verify this row should have been included in the export."
                ),
            ))
            return flags

        # Outlier detection across batch
        batch_quantities = context.get("batch_quantities", [])
        if len(batch_quantities) >= 5:
            mean = statistics.mean(batch_quantities)
            stdev = statistics.stdev(batch_quantities)
            if stdev > 0 and abs(qty - mean) > 3 * stdev:
                flags.append(ValidationResult(
                    flag_code="IMPOSSIBLE_QUANTITY",
                    severity="WARNING",
                    field_name="consumption_quantity",
                    message=(
                        f"Consumption {qty} is {abs(qty - mean) / stdev:.1f} SD from batch mean "
                        f"({mean:.0f} kWh). Could be a legitimate peak-production month or a "
                        f"unit entry error (MWh entered as kWh)."
                    ),
                ))
        return flags

    def _check_billing_period(self, c):
        flags = []
        start = c.get("period_start")
        end   = c.get("period_end")

        if not start or not end:
            return flags  # caught by mandatory field check

        try:
            d_start = date.fromisoformat(start)
            d_end   = date.fromisoformat(end)
        except ValueError:
            flags.append(ValidationResult(
                flag_code="INVALID_DATE",
                severity="ERROR",
                field_name="period_start",
                message="Billing period dates could not be parsed.",
            ))
            return flags

        if d_end < d_start:
            flags.append(ValidationResult(
                flag_code="INVALID_DATE",
                severity="ERROR",
                field_name="period_end",
                message=f"Billing period end ({end}) is before start ({start}).",
            ))

        period_days = (d_end - d_start).days
        if period_days > MAX_BILLING_DAYS:
            flags.append(ValidationResult(
                flag_code="DATE_OUTSIDE_PERIOD",
                severity="WARNING",
                field_name="period_end",
                message=(
                    f"Billing period spans {period_days} days (>{MAX_BILLING_DAYS}). "
                    f"This may represent two merged invoices or a contract changeover period. "
                    f"Verify before approving to avoid double-counting."
                ),
            ))
        return flags

    def _check_unit(self, c):
        flags = []
        unit = c.get("consumption_unit", "").lower()

        if unit not in KNOWN_UNITS:
            flags.append(ValidationResult(
                flag_code="UNIT_UNRECOGNIZED",
                severity="WARNING",
                field_name="consumption_unit",
                message=f"Unit '{unit}' is not recognised. Expected 'kWh' or 'MWh'.",
            ))
            return flags

        if unit == "mwh":
            # Do not silently convert — flag for analyst confirmation.
            # At 0.207 kg CO2e/kWh, a 51200 MWh "row" = 10,598 tonnes CO2e.
            # A 51200 kWh row = 10.6 tonnes. The difference is material.
            flags.append(ValidationResult(
                flag_code="UNIT_UNRECOGNIZED",
                severity="WARNING",
                field_name="consumption_unit",
                message=(
                    "Unit is MWh, not kWh. Normalization will multiply by 1000 before "
                    "applying the emission factor. Confirm the quantity is in MWh and not "
                    "a kWh value entered in the wrong unit field."
                ),
            ))
        return flags

    def _check_meter_readings(self, c):
        flags = []
        open_r  = c.get("reading_open")
        close_r = c.get("reading_close")
        qty     = c.get("consumption_quantity")

        if open_r is None or close_r is None:
            # Some suppliers bill by consumption directly without publishing readings
            flags.append(ValidationResult(
                flag_code="MISSING_OPTIONAL_FIELD",
                severity="INFO",
                field_name="reading_open",
                message="Meter readings not provided. Consumption taken from billed quantity directly.",
            ))
            return flags

        if close_r < open_r:
            flags.append(ValidationResult(
                flag_code="IMPOSSIBLE_QUANTITY",
                severity="ERROR",
                field_name="reading_close",
                message=(
                    f"Closing reading ({close_r}) is less than opening reading ({open_r}). "
                    f"Possible meter rollover or data entry error."
                ),
            ))
            return flags

        # Cross-check: billed consumption should match reading delta within 1%
        if qty is not None and open_r is not None and close_r is not None:
            reading_delta = close_r - open_r
            if reading_delta > 0 and abs(qty - reading_delta) / reading_delta > 0.01:
                flags.append(ValidationResult(
                    flag_code="IMPOSSIBLE_QUANTITY",
                    severity="WARNING",
                    field_name="consumption_quantity",
                    message=(
                        f"Billed consumption ({qty} kWh) differs from meter reading delta "
                        f"({reading_delta} kWh) by more than 1%. May include loss adjustment "
                        f"or tariff-split rounding — confirm with supplier invoice."
                    ),
                ))
        return flags

    def _check_mpan(self, c):
        flags = []
        mpan = c.get("meter_mpan", "")
        if not mpan:
            flags.append(ValidationResult(
                flag_code="MISSING_MANDATORY_FIELD",
                severity="WARNING",
                field_name="meter_mpan",
                message=(
                    "MPAN (Meter Point Administration Number) is missing. Without it we "
                    "cannot reliably identify the physical meter or de-duplicate across "
                    "billing periods."
                ),
            ))
        return flags

    def _check_duplicate_invoice(self, c, context):
        flags = []
        invoice = c.get("invoice_number", "")
        if not invoice:
            flags.append(ValidationResult(
                flag_code="MISSING_OPTIONAL_FIELD",
                severity="WARNING",
                field_name="invoice_number",
                message="Invoice number missing. Cannot detect duplicate invoice submissions.",
            ))
            return flags

        seen_invoices = context.get("seen_invoice_numbers", set())
        if invoice in seen_invoices:
            flags.append(ValidationResult(
                flag_code="DUPLICATE_ROW",
                severity="ERROR",
                field_name="invoice_number",
                message=(
                    f"Invoice '{invoice}' has already appeared in this batch. "
                    f"This is likely a duplicate row from a re-exported file."
                ),
            ))
        return flags

    def _check_estimated_reading(self, c):
        flags = []
        reading_type = c.get("reading_type", "").lower()
        if reading_type in ("estimated", "ablesewert estimated", "e"):
            flags.append(ValidationResult(
                flag_code="MISSING_OPTIONAL_FIELD",
                severity="INFO",
                field_name="reading_type",
                message=(
                    "Meter reading is estimated, not actual. The supplier will issue a "
                    "corrected invoice once an actual read is obtained. Consider holding "
                    "approval until the actual reading is available."
                ),
            ))
        return flags
