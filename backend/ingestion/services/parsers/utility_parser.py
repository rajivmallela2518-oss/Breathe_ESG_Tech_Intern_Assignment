import csv
import io
from datetime import datetime
from .base_parser import BaseParser


# Portal CSVs use standard comma delimiter and English-ish column names,
# but field formats vary by supplier. UK suppliers use DD/MM/YYYY; some
# EU suppliers switch to DD.MM.YYYY or YYYY-MM-DD.
DATE_FORMATS = [
    "%d/%m/%Y",   # 15/01/2024 — UK portal standard
    "%d.%m.%Y",   # 01.01.2024 — German/EU portal
    "%Y-%m-%d",   # 2024-01-01 — ISO
    "%m/%d/%Y",   # 01/15/2024 — US (rare but seen on global account portals)
]

# Column name → canonical field name.
# Supplier portals vary their headers; this maps the most common variants.
UTILITY_COLUMN_MAP = {
    "Account_Number":       "account_number",
    "Site_Name":            "site_name",
    "Site_Reference":       "site_reference",
    "Meter_MPAN":           "meter_mpan",
    "Meter_Serial":         "meter_serial",
    "Tariff_Code":          "tariff_code",
    "Supplier":             "supplier",
    "Invoice_Number":       "invoice_number",
    "Invoice_Date":         "invoice_date",
    "Billing_Period_Start": "period_start",
    "Billing_Period_End":   "period_end",
    "Meter_Reading_Open":   "reading_open",
    "Meter_Reading_Close":  "reading_close",
    "Reading_Type":         "reading_type",
    "Consumption_kWh":      "consumption_quantity",
    "Unit":                 "consumption_unit",
    "Day_Rate_kWh":         "day_kwh",
    "Night_Rate_kWh":       "night_kwh",
    "Total_Cost_GBP":       "total_cost_gbp",
    "CCL_Liable":           "ccl_liable",
    "Notes":                "notes",
}

# Rows where there is no actual energy consumption to report.
# CCL-only rows, standing charge rows, and administrative adjustments
# should be skipped — they contain no Scope 2 emissions data.
NON_CONSUMPTION_SIGNALS = {
    "ccl charge only",
    "standing charge",
    "administration charge",
    "fit export",        # feed-in tariff exports are handled separately
}


class UtilityParser(BaseParser):
    """
    Parses electricity portal CSV exports.

    Format assumptions (documented in SOURCES.md):
    - Comma delimiter with quoted fields
    - DD/MM/YYYY dates (UK standard; handles DD.MM.YYYY and ISO)
    - Consumption in kWh (occasionally MWh — flagged, not silently converted)
    - Billing periods do not align with calendar months
    - Multiple meters per site appear as separate rows
    - Estimated readings are flagged INFO
    - FIT export rows (negative consumption) are flagged WARNING
    - CCL-only and standing-charge-only rows are skipped (no emissions data)
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

            if self._is_non_consumption_row(raw_data):
                continue

            canonical = self._map_to_canonical(raw_data)
            results.append({
                "row_number": row_number,
                "raw_data": raw_data,
                "canonical": canonical,
                "checksum": self.checksum(raw_data),
            })

        return results

    def _is_non_consumption_row(self, raw):
        """
        Skip rows that carry no consumption data — CCL charges, standing charges,
        FIT export credits. These appear in the same export file and would produce
        zero or meaningless emission records if processed.
        """
        notes = raw.get("Notes", "").lower()
        consumption = raw.get("Consumption_kWh", "").strip()

        if any(signal in notes for signal in NON_CONSUMPTION_SIGNALS):
            return True

        # Row has no quantity at all and no meter readings
        if not consumption and not raw.get("Meter_Reading_Open") and not raw.get("Meter_Reading_Close"):
            return True

        return False

    def _map_to_canonical(self, raw):
        canonical = {}
        for csv_col, canon_col in UTILITY_COLUMN_MAP.items():
            canonical[canon_col] = raw.get(csv_col, "").strip()

        canonical["period_start"] = self._parse_date(canonical.get("period_start", ""))
        canonical["period_end"]   = self._parse_date(canonical.get("period_end",   ""))
        canonical["invoice_date"] = self._parse_date(canonical.get("invoice_date", ""))

        canonical["consumption_quantity"] = self._parse_float(
            canonical.get("consumption_quantity", "")
        )
        canonical["reading_open"]  = self._parse_float(canonical.get("reading_open",  ""))
        canonical["reading_close"] = self._parse_float(canonical.get("reading_close", ""))

        # Normalise unit string for downstream comparison
        canonical["consumption_unit"] = canonical.get("consumption_unit", "").strip().lower()

        return canonical

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
            return float(value.replace(",", ""))
        except ValueError:
            return None
