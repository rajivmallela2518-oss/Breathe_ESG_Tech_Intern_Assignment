import uuid
from django.db import models


class UploadBatch(models.Model):
    SOURCE_TYPES = [
        ("SAP_FUEL",            "SAP Fuel & Procurement"),
        ("UTILITY_ELECTRICITY", "Utility Electricity"),
        ("CORPORATE_TRAVEL",    "Corporate Travel"),
    ]
    STATUS = [
        ("PROCESSING", "Processing"),
        ("COMPLETE",   "Complete"),
        ("FAILED",     "Failed"),
    ]

    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant         = models.ForeignKey("tenants.Tenant", on_delete=models.CASCADE)
    uploaded_by    = models.ForeignKey("users.TenantUser", on_delete=models.PROTECT)
    source_type    = models.CharField(max_length=30, choices=SOURCE_TYPES)
    original_filename = models.CharField(max_length=500)
    file_hash      = models.CharField(max_length=64)
    status         = models.CharField(max_length=20, choices=STATUS, default="PROCESSING")
    total_rows     = models.IntegerField(default=0)
    valid_rows     = models.IntegerField(default=0)
    flagged_rows   = models.IntegerField(default=0)
    failed_rows    = models.IntegerField(default=0)
    error_message  = models.TextField(null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    completed_at   = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"UploadBatch {self.id} / {self.source_type} / {self.created_at:%Y-%m-%d}"

    class Meta:
        db_table = "ingestion_uploadbatch"
        indexes  = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "source_type"]),
            models.Index(fields=["file_hash"]),
        ]


class RawRow(models.Model):
    ROW_STATUS = [
        ("PENDING",  "Pending Validation"),
        ("VALID",    "Valid"),
        ("FLAGGED",  "Flagged"),
        ("FAILED",   "Failed"),
    ]

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant      = models.ForeignKey("tenants.Tenant", on_delete=models.CASCADE)
    batch       = models.ForeignKey(UploadBatch, on_delete=models.CASCADE, related_name="rows")
    row_number  = models.IntegerField()
    source_type = models.CharField(max_length=30)
    raw_data    = models.JSONField()
    status      = models.CharField(max_length=25, choices=ROW_STATUS, default="PENDING")
    checksum    = models.CharField(max_length=32)
    created_at  = models.DateTimeField(auto_now_add=True)

    # In-memory only — set by parse_service after bulk_create, never persisted.
    # Keeps canonical parsed data co-located with the raw row during the
    # validate → normalize pipeline without storing it twice in the DB.
    canonical_data: dict = {}

    def __str__(self):
        return f"RawRow {self.row_number} / {self.source_type} / batch {self.batch_id}"

    class Meta:
        db_table = "ingestion_rawrow"
        indexes  = [
            models.Index(fields=["tenant", "batch"]),
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["checksum"]),
            models.Index(fields=["tenant", "source_type", "status"]),
        ]


class ValidationFlag(models.Model):
    SEVERITY = [("ERROR", "Error"), ("WARNING", "Warning"), ("INFO", "Info")]
    FLAG_CODES = [
        ("MISSING_MANDATORY_FIELD", "Missing Mandatory Field"),
        ("DUPLICATE_ROW",           "Duplicate Row"),
        ("INVALID_DATE",            "Invalid Date"),
        ("NEGATIVE_QUANTITY",       "Negative Quantity"),
        ("IMPOSSIBLE_QUANTITY",     "Statistically Impossible Quantity"),
        ("UNIT_UNRECOGNIZED",       "Unrecognized Unit"),
        ("MISSING_OPTIONAL_FIELD",  "Missing Optional Field"),
        ("DATE_OUTSIDE_PERIOD",     "Date Outside Expected Period"),
    ]

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant     = models.ForeignKey("tenants.Tenant", on_delete=models.CASCADE)
    raw_row    = models.ForeignKey(RawRow, on_delete=models.CASCADE, related_name="flags")
    flag_code  = models.CharField(max_length=30, choices=FLAG_CODES)
    severity   = models.CharField(max_length=10, choices=SEVERITY)
    field_name = models.CharField(max_length=100, null=True, blank=True)
    message    = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.severity}: {self.flag_code} on row {self.raw_row_id}"

    class Meta:
        db_table = "ingestion_validationflag"
        indexes  = [
            models.Index(fields=["raw_row"]),
            models.Index(fields=["tenant", "flag_code"]),
            models.Index(fields=["tenant", "severity"]),
        ]
