"""
Validation engine for ESG ingestion.

Orchestrates per-source rule checks and cross-batch duplicate detection.
Every row exits this service with status VALID, FLAGGED, or FAILED and
zero or more ValidationFlag records attached to it.

Rule severity contract:
  ERROR   — row cannot be normalised; blocked from approval until resolved
  WARNING — row can be approved but analyst must explicitly review
  INFO    — informational only; no blocking action required

A row is FLAGGED if it has any ERROR or WARNING flag.
A row is FAILED if it raised an exception during parsing or rule execution.
A row is VALID only if it has zero ERROR/WARNING flags (INFO flags are allowed).
"""

import statistics
from ingestion.models import ValidationFlag, RawRow
from ingestion.validators.sap_validator import SAPValidator
from ingestion.validators.utility_validator import UtilityValidator
from ingestion.validators.travel_validator import TravelValidator

VALIDATOR_MAP = {
    "SAP_FUEL":            SAPValidator,
    "UTILITY_ELECTRICITY": UtilityValidator,
    "CORPORATE_TRAVEL":    TravelValidator,
}

# Quantity field names per source type — used to build batch statistics
# for outlier detection before individual rows are processed.
QUANTITY_FIELDS = {
    "SAP_FUEL":            "quantity",
    "UTILITY_ELECTRICITY": "consumption_quantity",
    "CORPORATE_TRAVEL":    "distance_km",
}


def validate_batch(raw_rows, source_type, tenant):
    """
    Main entry point called by parse_service after bulk_create.

    Builds batch-level context, then processes each row through the
    appropriate validator. Writes ValidationFlag records, sets row.status,
    and bulk-saves status updates in a single query at the end.

    Returns summary dict: { total, valid, flagged, failed }
    """
    validator_cls = VALIDATOR_MAP.get(source_type)
    if not validator_cls:
        raise ValueError(f"No validator registered for source_type='{source_type}'")

    validator = validator_cls()
    qty_field = QUANTITY_FIELDS.get(source_type, "quantity")

    # ---- Build batch-level context ----------------------------------------
    # Collect quantities for outlier detection (needs full batch picture first)
    batch_quantities = []
    for row in raw_rows:
        val = row.canonical_data.get(qty_field)
        if val is not None and isinstance(val, (int, float)) and val >= 0:
            batch_quantities.append(float(val))

    # Collect checksums for within-batch duplicate detection
    seen_checksums = set()

    # Collect invoice numbers for utility duplicate detection
    seen_invoice_numbers = set()

    # ---- Cross-batch duplicate check: fetch existing checksums from DB ----
    # This catches rows that were already ingested in a prior upload batch.
    existing_checksums = set(
        RawRow.objects.filter(
            tenant=tenant,
            source_type=source_type,
            status__in=("VALID", "FLAGGED"),  # don't count previously-failed rows
        ).values_list("checksum", flat=True)
    )

    # ---- Process each row -------------------------------------------------
    flags_to_create = []
    status_updates  = {}  # row_id → new status

    for row in raw_rows:
        context = {
            "batch_quantities":     batch_quantities,
            "seen_checksums":       seen_checksums | existing_checksums,
            "seen_invoice_numbers": seen_invoice_numbers,
            "current_checksum":     row.checksum,
        }

        try:
            results = validator.check(row.canonical_data, context)
        except Exception as exc:
            # Unexpected rule execution error — mark row FAILED so it doesn't
            # silently produce a bad emission record
            status_updates[row.id] = "FAILED"
            flags_to_create.append(ValidationFlag(
                tenant=tenant,
                raw_row=row,
                flag_code="MISSING_MANDATORY_FIELD",
                severity="ERROR",
                field_name=None,
                message=f"Validation rule raised an unexpected error: {exc}",
            ))
            continue

        # Track state for duplicate detection on subsequent rows
        seen_checksums.add(row.checksum)
        invoice = row.canonical_data.get("invoice_number", "")
        if invoice:
            seen_invoice_numbers.add(invoice)

        # Separate errors/warnings from info-only flags
        blocking_flags = [r for r in results if r.severity in ("ERROR", "WARNING")]
        info_flags     = [r for r in results if r.severity == "INFO"]

        new_status = "FLAGGED" if blocking_flags else "VALID"
        status_updates[row.id] = new_status

        for result in results:
            flags_to_create.append(ValidationFlag(
                tenant=tenant,
                raw_row=row,
                flag_code=result.flag_code,
                severity=result.severity,
                field_name=result.field_name,
                message=result.message,
            ))

    # ---- Persist in bulk --------------------------------------------------
    if flags_to_create:
        ValidationFlag.objects.bulk_create(flags_to_create)

    # Bulk-update statuses: group by status to use update() instead of N saves
    valid_ids   = [rid for rid, s in status_updates.items() if s == "VALID"]
    flagged_ids = [rid for rid, s in status_updates.items() if s == "FLAGGED"]
    failed_ids  = [rid for rid, s in status_updates.items() if s == "FAILED"]

    if valid_ids:
        RawRow.objects.filter(id__in=valid_ids).update(status="VALID")
    if flagged_ids:
        RawRow.objects.filter(id__in=flagged_ids).update(status="FLAGGED")
    if failed_ids:
        RawRow.objects.filter(id__in=failed_ids).update(status="FAILED")

    # Keep in-memory status current for the normalization pass that follows
    for row in raw_rows:
        row.status = status_updates.get(row.id, row.status)

    return {
        "total":   len(raw_rows),
        "valid":   len(valid_ids),
        "flagged": len(flagged_ids),
        "failed":  len(failed_ids),
    }


def get_flag_summary(batch_id, tenant):
    """
    Returns flag counts by code and severity for a batch.
    Used by the dashboard summary endpoint.
    """
    from django.db.models import Count
    return (
        ValidationFlag.objects
        .filter(raw_row__batch_id=batch_id, tenant=tenant)
        .values("flag_code", "severity")
        .annotate(count=Count("id"))
        .order_by("severity", "flag_code")
    )
