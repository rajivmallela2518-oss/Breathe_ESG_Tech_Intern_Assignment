import csv
import io
from datetime import datetime
from .base_parser import BaseParser


# SAP flat file exports use semicolons in European locales.
# German locale exports use comma as decimal separator and period as thousands.
# This parser handles both.

# Maps the German/mixed SAP column names to canonical field names.
# Real SAP exports vary by client config — this covers the most common
# MB52/ME2M flat file variant used by sustainability teams.
SAP_COLUMN_MAP = {
    "MANDT":       "sap_client",
    "BUKRS":       "company_code",
    "WERKS":       "plant_code",
    "Plant_Name":  "plant_name",
    "MATNR":       "material_number",
    "MAKTX":       "material_description",
    "BWART":       "movement_type",
    "BLDAT":       "document_date",
    "BUDAT":       "posting_date",
    "MENGE":       "quantity",
    "MEINS":       "unit",
    "ERFMG":       "entry_quantity",
    "ERFME":       "entry_unit",
    "KOSTL":       "cost_center",
    "AUFNR":       "order_number",
    "LIFNR":       "vendor_id",
    "Vendor_Name": "vendor_name",
}

# SAP date formats found in the wild, in order of try priority
DATE_FORMATS = [
    "%Y%m%d",       # 20240103  — standard SAP internal format
    "%d.%m.%Y",     # 03.01.2024 — German locale display format
    "%Y-%m-%d",     # 2024-01-05 — ISO, occasionally output by newer SAP versions
    "%m/%d/%Y",     # 01/03/2024 — US locale, rare but exists
]

# Goods issue movement type — the only movement that represents consumption
# 201 = Goods issue to cost centre (fuel/procurement consumption)
# 261 = Goods issue for order
CONSUMPTION_MOVEMENT_TYPES = {"201", "261"}


class SAPParser(BaseParser):
    """
    Parses SAP MB52/ME2M style flat file exports.

    Format assumptions (documented in SOURCES.md):
    - Semicolon delimiter (European SAP default)
    - German or English column headers mixed depending on SAP client language
    - MENGE may use comma as decimal separator (German locale)
    - Dates in YYYYMMDD, DD.MM.YYYY, or YYYY-MM-DD
    - Only movement types 201/261 represent actual fuel/procurement consumption
    - Duplicate rows occur from re-exports — detected by checksum
    """

    def parse(self, file_obj):
        if isinstance(file_obj, (bytes, bytearray)):
            file_obj = io.TextIOWrapper(io.BytesIO(file_obj), encoding="utf-8-sig")

        # utf-8-sig strips the BOM that SAP sometimes prepends
        content = file_obj.read()
        if isinstance(content, bytes):
            content = content.decode("utf-8-sig", errors="replace")

        reader = csv.DictReader(
            io.StringIO(content),
            delimiter=";",
            quoting=csv.QUOTE_MINIMAL,
        )

        results = []
        for row_number, raw_row in enumerate(reader, start=1):
            # Strip whitespace from all keys and values (SAP adds trailing spaces)
            raw_data = {k.strip(): v.strip() for k, v in raw_row.items() if k}

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
        for sap_col, canon_col in SAP_COLUMN_MAP.items():
            canonical[canon_col] = raw.get(sap_col, "").strip()

        canonical["document_date"] = self._parse_date(canonical.get("document_date", ""))
        canonical["posting_date"]  = self._parse_date(canonical.get("posting_date",  ""))
        canonical["quantity"]      = self._parse_decimal(canonical.get("quantity", ""))
        canonical["material_number"] = canonical.get("material_number", "").lstrip("0") or None

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
        return None  # returned as-is for the validator to flag

    @staticmethod
    def _parse_decimal(value):
        """
        Handle both German locale (6100,000) and standard (6100.000) decimal formats.
        SAP German exports use comma as the decimal separator.
        """
        if not value:
            return None
        cleaned = value.replace(" ", "").replace(" ", "")  # strip non-breaking spaces
        # Detect German format: comma as decimal, period as thousands
        # "6.100,000" → 6100.0   |   "6100,000" → 6100.0   |   "6100.000" → 6100.0
        if "," in cleaned and "." in cleaned:
            # Both present — period is thousands separator, comma is decimal
            cleaned = cleaned.replace(".", "").replace(",", ".")
        elif "," in cleaned:
            # Only comma — it's the decimal separator
            cleaned = cleaned.replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            return None
