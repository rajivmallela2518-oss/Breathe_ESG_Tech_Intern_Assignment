import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


class TenantUser(AbstractUser):
    id        = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant    = models.ForeignKey("tenants.Tenant", on_delete=models.CASCADE, related_name="users")
    full_name = models.CharField(max_length=255)
    role      = models.CharField(
        max_length=20,
        choices=[("ANALYST", "Analyst"), ("ADMIN", "Admin")],
        default="ANALYST",
    )

    username = None
    email    = models.EmailField(unique=True)

    USERNAME_FIELD  = "email"
    REQUIRED_FIELDS = ["full_name"]

    def __str__(self):
        return f"{self.full_name} ({self.tenant})"

    class Meta:
        db_table = "users_tenantuser"
