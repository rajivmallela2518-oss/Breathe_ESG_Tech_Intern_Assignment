import uuid
from django.db import models


class ReviewDecision(models.Model):
    STATUS = [
        ("PENDING",  "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
    ]

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant       = models.ForeignKey("tenants.Tenant", on_delete=models.CASCADE)
    emission     = models.OneToOneField(
        "emissions.NormalizedEmission",
        on_delete=models.CASCADE,
        related_name="review",
    )
    status       = models.CharField(max_length=20, choices=STATUS, default="PENDING")
    analyst      = models.ForeignKey(
        "users.TenantUser",
        on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    analyst_note = models.TextField(null=True, blank=True)
    reviewed_at  = models.DateTimeField(null=True, blank=True)
    is_locked    = models.BooleanField(default=False)
    created_at   = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"ReviewDecision {self.status} / emission {self.emission_id}"

    class Meta:
        db_table = "reviews_reviewdecision"
        indexes  = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "analyst"]),
            models.Index(fields=["tenant", "is_locked"]),
        ]
