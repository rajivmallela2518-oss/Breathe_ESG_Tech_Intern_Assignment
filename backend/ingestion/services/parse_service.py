import hashlib
from django.utils import timezone
from ingestion.models import UploadBatch, RawRow
from ingestion.services.parsers.sap_parser import SAPParser
from ingestion.services.parsers.utility_parser import UtilityParser
from ingestion.services.parsers.travel_parser import TravelParser
from ingestion.services.validation_service import validate_batch
from emissions.services.normalization_service import normalize_batch
from audit.services import audit_service

PARSER_MAP = {
    "SAP_FUEL":            SAPParser,
    "UTILITY_ELECTRICITY": UtilityParser,
    "CORPORATE_TRAVEL":    TravelParser,
}


def process_upload(file_obj, source_type, tenant, user):
    """
    Full ingestion pipeline for a single file upload.

    Steps:
      1. Hash the file for duplicate upload detection
      2. Create UploadBatch record
      3. Parse raw rows via source-specific parser
      4. Bulk-create RawRow records (raw_data = original JSON)
      5. Run validation rules — writes ValidationFlag records, sets row.status
      6. Run normalization on VALID rows — writes NormalizedEmission + ReviewDecision
      7. Update batch counters and status
      8. Write audit log

    Returns the completed UploadBatch instance.
    """
    file_bytes = file_obj.read()
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    batch = UploadBatch.objects.create(
        tenant=tenant,
        uploaded_by=user,
        source_type=source_type,
        original_filename=getattr(file_obj, "name", "upload.csv"),
        file_hash=file_hash,
        status="PROCESSING",
    )

    try:
        parser_cls = PARSER_MAP.get(source_type)
        if not parser_cls:
            raise ValueError(f"Unknown source_type: {source_type}")

        import io
        parsed_rows = parser_cls().parse(io.BytesIO(file_bytes))

        # Bulk-create all raw rows in one query
        raw_row_objs = [
            RawRow(
                tenant=tenant,
                batch=batch,
                row_number=row["row_number"],
                source_type=source_type,
                raw_data=row["raw_data"],
                checksum=row["checksum"],
                status="PENDING",
            )
            for row in parsed_rows
        ]
        created = RawRow.objects.bulk_create(raw_row_objs)

        # Attach canonical data in-memory (not persisted — only raw_data is stored)
        canonical_map = {row["row_number"]: row["canonical"] for row in parsed_rows}
        for raw_row in created:
            raw_row.canonical_data = canonical_map.get(raw_row.row_number, {})

        # Validation pass
        validate_batch(created, source_type, tenant)

        # Normalization pass (valid rows only)
        valid_rows = [r for r in created if r.status == "VALID"]
        normalize_batch(valid_rows, source_type, tenant)

        # Update batch counters
        batch.total_rows = len(created)
        batch.valid_rows = sum(1 for r in created if r.status == "VALID")
        batch.flagged_rows = sum(1 for r in created if r.status == "FLAGGED")
        batch.failed_rows = sum(1 for r in created if r.status == "FAILED")
        batch.status = "COMPLETE"
        batch.completed_at = timezone.now()
        batch.save()

        audit_service.log(
            tenant=tenant,
            action="BATCH_INGESTED",
            obj=batch,
            actor=user,
            after={
                "total_rows": batch.total_rows,
                "valid_rows": batch.valid_rows,
                "flagged_rows": batch.flagged_rows,
            },
        )

    except Exception as exc:
        batch.status = "FAILED"
        batch.error_message = str(exc)
        batch.completed_at = timezone.now()
        batch.save()
        raise

    return batch
