from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from django.db.models import Sum, Count, Q

from tenants.mixins import TenantQuerySetMixin
from .models import UploadBatch, RawRow, ValidationFlag
from .serializers import UploadBatchSerializer, RawRowSerializer, UploadResponseSerializer
from .services.parse_service import process_upload


class UploadView(APIView):
    """
    POST /api/v1/ingestion/upload/

    Accepts a multipart file upload with source_type.
    Runs the full parse → validate → normalize pipeline synchronously.
    Returns row counts and batch ID so the frontend can navigate to review.
    """
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        file_obj    = request.FILES.get("file")
        source_type = request.data.get("source_type", "").upper()

        if not file_obj:
            return Response({"detail": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)

        valid_types = {"SAP_FUEL", "UTILITY_ELECTRICITY", "CORPORATE_TRAVEL"}
        if source_type not in valid_types:
            return Response(
                {"detail": f"source_type must be one of {sorted(valid_types)}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            batch = process_upload(
                file_obj=file_obj,
                source_type=source_type,
                tenant=request.tenant,
                user=request.user,
            )
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        return Response(
            {
                "batch_id":    str(batch.id),
                "total_rows":  batch.total_rows,
                "valid_rows":  batch.valid_rows,
                "flagged_rows": batch.flagged_rows,
                "failed_rows": batch.failed_rows,
                "status":      batch.status,
            },
            status=status.HTTP_201_CREATED,
        )


class BatchListView(TenantQuerySetMixin, ListAPIView):
    """GET /api/v1/ingestion/batches/"""
    queryset         = UploadBatch.objects.all().order_by("-created_at")
    serializer_class = UploadBatchSerializer


class BatchDetailView(TenantQuerySetMixin, RetrieveAPIView):
    """GET /api/v1/ingestion/batches/<id>/"""
    queryset         = UploadBatch.objects.all()
    serializer_class = UploadBatchSerializer


class BatchRowsView(TenantQuerySetMixin, ListAPIView):
    """
    GET /api/v1/ingestion/batches/<id>/rows/

    Returns raw rows for a batch, optionally filtered by status.
    Used by the review page to show what came in and what was flagged.
    """
    serializer_class = RawRowSerializer

    def get_queryset(self):
        qs     = RawRow.objects.filter(
            tenant=self.request.tenant,
            batch_id=self.kwargs["pk"],
        ).prefetch_related("flags").order_by("row_number")
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter.upper())
        return qs


class SuspiciousRowsView(APIView):
    """
    GET /api/v1/ingestion/suspicious/

    Returns all FLAGGED rows across the tenant with their ERROR/WARNING flags
    embedded. Supports optional ?source_type= and ?severity= filters.
    Used by the analyst dashboard to surface rows that need attention.
    """

    def get(self, request):
        tenant = request.tenant
        severity = request.query_params.get("severity", "").upper()
        source_type = request.query_params.get("source_type", "").upper()

        rows_qs = (
            RawRow.objects
            .filter(tenant=tenant, status="FLAGGED")
            .prefetch_related("flags", "batch")
            .order_by("-created_at")
        )
        if source_type:
            rows_qs = rows_qs.filter(source_type=source_type)

        if severity in ("ERROR", "WARNING", "INFO"):
            rows_qs = rows_qs.filter(flags__severity=severity).distinct()

        serializer = RawRowSerializer(rows_qs, many=True)
        return Response(serializer.data)


class DashboardSummaryView(APIView):
    """
    GET /api/v1/ingestion/summary/

    Aggregate counts for the analyst dashboard.
    Returns total/pending/flagged/approved across the tenant.
    """

    def get(self, request):
        from reviews.models import ReviewDecision

        tenant = request.tenant

        total_rows = RawRow.objects.filter(tenant=tenant).count()
        pending    = ReviewDecision.objects.filter(tenant=tenant, status="PENDING").count()
        approved   = ReviewDecision.objects.filter(tenant=tenant, status="APPROVED").count()
        rejected   = ReviewDecision.objects.filter(tenant=tenant, status="REJECTED").count()
        flagged    = RawRow.objects.filter(tenant=tenant, status="FLAGGED").count()

        return Response({
            "total_rows": total_rows,
            "pending":    pending,
            "approved":   approved,
            "rejected":   rejected,
            "flagged":    flagged,
        })
