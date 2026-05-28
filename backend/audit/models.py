import uuid
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class AuditLog(models.Model):
    ACTIONS = [
        ("BATCH_INGESTED", "Batch Ingested"),
        ("ROW_VALIDATED",  "Row Validated"),
        ("ROW_FLAGGED",    "Row Flagged"),
        ("ROW_NORMALIZED", "Row Normalized"),
        ("ROW_APPROVED",   "Row Approved"),
        ("ROW_REJECTED",   "Row Rejected"),
        ("NOTE_EDITED",    "Analyst Note Edited"),
        ("ROW_UNLOCKED",   "Row Unlocked by Admin"),
    ]

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant       = models.ForeignKey("tenants.Tenant", on_delete=models.CASCADE)
    actor        = models.ForeignKey(
        "users.TenantUser",
        on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    action       = models.CharField(max_length=40, choices=ACTIONS)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id    = models.UUIDField()
    content_object = GenericForeignKey("content_type", "object_id")
    object_repr  = models.CharField(max_length=300)
    before_state = models.JSONField(null=True, blank=True)
    after_state  = models.JSONField(null=True, blank=True)
    timestamp    = models.DateTimeField(auto_now_add=True)
    ip_address   = models.GenericIPAddressField(null=True, blank=True)

    def __str__(self):
        return f"{self.action} by {self.actor} at {self.timestamp:%Y-%m-%d %H:%M}"

    class Meta:
        db_table = "audit_auditlog"
        indexes  = [
            models.Index(fields=["tenant", "-timestamp"]),
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["tenant", "actor"]),
            models.Index(fields=["tenant", "action"]),
        ]
