from rest_framework.generics import ListAPIView
from tenants.mixins import TenantQuerySetMixin
from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogView(TenantQuerySetMixin, ListAPIView):
    """
    GET /api/v1/audit/

    Read-only chronological audit trail for the tenant.
    No write endpoint — audit records are append-only by design.
    """
    queryset         = AuditLog.objects.all().select_related("actor").order_by("-timestamp")
    serializer_class = AuditLogSerializer
