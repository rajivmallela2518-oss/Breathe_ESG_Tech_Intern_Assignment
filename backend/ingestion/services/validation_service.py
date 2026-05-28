from ingestion.validators.sap_validator import SAPValidator
from ingestion.validators.utility_validator import UtilityValidator
from ingestion.validators.travel_validator import TravelValidator
from ingestion.models import ValidationFlag

VALIDATOR_MAP = {
    "SAP_FUEL":            SAPValidator,
    "UTILITY_ELECTRICITY": UtilityValidator,
    "CORPORATE_TRAVEL":    TravelValidator,
}


def validate_batch(raw_rows, source_type, tenant):
    """
    Run validation rules against all parsed rows in a batch.

    Builds batch-level context (quantities for outlier detection,
    seen checksums for duplicate detection) before processing each row
    so statistical checks have the full batch picture.

    Returns a dict:  { raw_row_id: [ValidationFlag], ... }
    """
    validator_cls = VALIDATOR_MAP.get(source_type)
    if not validator_cls:
        raise ValueError(f"No validator registered for source_type '{source_type}'")

    validator = validator_cls()

    # Pre-compute batch-level context
    batch_quantities = [
        r.raw_data_canonical.get("quantity")
        for r in raw_rows
        if r.raw_data_canonical.get("quantity") is not None
    ]
    seen_checksums = set()
    flags_by_row = {}

    for raw_row in raw_rows:
        context = {
            "batch_quantities": [q for q in batch_quantities if q is not None],
            "seen_checksums": seen_checksums,
            "current_checksum": raw_row.checksum,
        }
        results = validator.check(raw_row.canonical_data, context)
        seen_checksums.add(raw_row.checksum)

        db_flags = []
        for r in results:
            db_flags.append(
                ValidationFlag(
                    tenant=tenant,
                    raw_row=raw_row,
                    flag_code=r.flag_code,
                    severity=r.severity,
                    field_name=r.field_name,
                    message=r.message,
                )
            )

        if db_flags:
            ValidationFlag.objects.bulk_create(db_flags)
            raw_row.status = "FLAGGED"
        else:
            raw_row.status = "VALID"

        raw_row.save(update_fields=["status"])
        flags_by_row[raw_row.id] = db_flags

    return flags_by_row
