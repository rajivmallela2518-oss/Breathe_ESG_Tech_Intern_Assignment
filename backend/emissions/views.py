from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Sum, Count

from tenants.mixins import TenantQuerySetMixin
from .models import NormalizedEmission
from .serializers import NormalizedEmissionSerializer


class EmissionListView(TenantQuerySetMixin, ListAPIView):
    """
    GET /api/v1/emissions/?scope=1&source_type=SAP_FUEL

    Read-only list of all normalised emissions for the tenant.
    Supports filtering by scope and source type.
    """
    serializer_class = NormalizedEmissionSerializer

    def get_queryset(self):
        qs = (
            NormalizedEmission.objects
            .filter(tenant=self.request.tenant)
            .select_related("emission_factor", "batch", "review")
            .order_by("-period_start")
        )
        scope = self.request.query_params.get("scope")
        if scope:
            qs = qs.filter(scope=int(scope))
        source_type = self.request.query_params.get("source_type")
        if source_type:
            qs = qs.filter(batch__source_type=source_type.upper())
        return qs


class EmissionDetailView(TenantQuerySetMixin, RetrieveAPIView):
    """GET /api/v1/emissions/<id>/"""
    queryset         = NormalizedEmission.objects.all().select_related("emission_factor", "batch", "review")
    serializer_class = NormalizedEmissionSerializer


class EmissionScopeBreakdownView(APIView):
    """
    GET /api/v1/emissions/scope-breakdown/

    Returns total kg_co2e grouped by scope and source type.
    Used for the dashboard summary chart (if added).
    """

    def get(self, request):
        tenant = request.tenant
        approved_only = request.query_params.get("approved_only", "false").lower() == "true"

        qs = NormalizedEmission.objects.filter(tenant=tenant)
        if approved_only:
            qs = qs.filter(review__status="APPROVED")

        breakdown = (
            qs.values("scope", "batch__source_type")
            .annotate(total_kg_co2e=Sum("kg_co2e"), row_count=Count("id"))
            .order_by("scope", "batch__source_type")
        )

        return Response(list(breakdown))
