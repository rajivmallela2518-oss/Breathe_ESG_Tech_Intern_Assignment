from rest_framework import serializers
from .models import ReviewDecision
from ingestion.serializers import ValidationFlagSerializer


class ReviewQueueSerializer(serializers.ModelSerializer):
    """
    Flat serializer for the analyst review table.
    Joins emission and raw row data so the frontend needs one API call per page.
    """
    emission_id         = serializers.UUIDField(source="emission.id")
    scope               = serializers.IntegerField(source="emission.scope")
    activity_type       = serializers.CharField(source="emission.activity_type")
    period_start        = serializers.DateField(source="emission.period_start")
    period_end          = serializers.DateField(source="emission.period_end")
    quantity_normalized = serializers.DecimalField(
        source="emission.quantity_normalized", max_digits=15, decimal_places=4
    )
    unit_normalized     = serializers.CharField(source="emission.unit_normalized")
    kg_co2e             = serializers.DecimalField(
        source="emission.kg_co2e", max_digits=15, decimal_places=6
    )
    source_label        = serializers.CharField(source="emission.source_label")
    source_type         = serializers.CharField(source="emission.batch.source_type")
    location            = serializers.CharField(source="emission.location")
    flags               = serializers.SerializerMethodField()
    review_status       = serializers.CharField(source="status")
    analyst_note        = serializers.CharField()

    def get_flags(self, obj):
        flags = obj.emission.raw_row.flags.all()
        return ValidationFlagSerializer(flags, many=True).data

    class Meta:
        model  = ReviewDecision
        fields = [
            "id", "emission_id", "review_status", "analyst_note", "is_locked",
            "reviewed_at", "scope", "activity_type", "period_start", "period_end",
            "quantity_normalized", "unit_normalized", "kg_co2e", "source_label",
            "source_type", "location", "flags",
        ]


class ApproveSerializer(serializers.Serializer):
    pass  # no body needed — approve is a side-effect-only POST


class RejectSerializer(serializers.Serializer):
    note = serializers.CharField(min_length=5)
