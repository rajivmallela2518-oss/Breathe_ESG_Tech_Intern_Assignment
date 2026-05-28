from rest_framework.generics import ListAPIView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from tenants.mixins import TenantQuerySetMixin
from .models import ReviewDecision
from .serializers import ReviewQueueSerializer, RejectSerializer
from .services.review_service import approve, reject


class ReviewQueueView(TenantQuerySetMixin, ListAPIView):
    """
    GET /api/v1/reviews/?status=PENDING

    Returns paginated list of review decisions with embedded emission data
    and flags. Default filter: PENDING. Supports status=APPROVED|REJECTED.
    """
    serializer_class = ReviewQueueSerializer

    def get_queryset(self):
        qs = (
            ReviewDecision.objects
            .filter(tenant=self.request.tenant)
            .select_related(
                "emission",
                "emission__raw_row",
                "emission__batch",
                "analyst",
            )
            .prefetch_related("emission__raw_row__flags")
            .order_by("-emission__created_at")
        )
        status_filter = self.request.query_params.get("status", "PENDING").upper()
        return qs.filter(status=status_filter)


class ApproveView(APIView):
    """POST /api/v1/reviews/<id>/approve/"""

    def post(self, request, pk):
        try:
            decision = ReviewDecision.objects.select_related("emission").get(
                id=pk, tenant=request.tenant
            )
        except ReviewDecision.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            approve(
                emission=decision.emission,
                analyst=request.user,
                ip=request.META.get("REMOTE_ADDR"),
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"status": "APPROVED"})


class RejectView(APIView):
    """POST /api/v1/reviews/<id>/reject/"""

    def post(self, request, pk):
        serializer = RejectSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            decision = ReviewDecision.objects.select_related("emission").get(
                id=pk, tenant=request.tenant
            )
        except ReviewDecision.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            reject(
                emission=decision.emission,
                analyst=request.user,
                note=serializer.validated_data["note"],
                ip=request.META.get("REMOTE_ADDR"),
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"status": "REJECTED"})
