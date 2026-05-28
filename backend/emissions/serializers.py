from rest_framework import serializers
from .models import NormalizedEmission, EmissionFactor


class EmissionFactorSerializer(serializers.ModelSerializer):
    class Meta:
        model  = EmissionFactor
        fields = ["id", "activity_type", "scope", "unit", "kg_co2e_per_unit", "source_reference", "valid_from"]


class NormalizedEmissionSerializer(serializers.ModelSerializer):
    review_status   = serializers.CharField(source="review.status",       read_only=True, default=None)
    analyst_note    = serializers.CharField(source="review.analyst_note", read_only=True, default=None)
    is_locked       = serializers.BooleanField(source="review.is_locked", read_only=True, default=False)
    emission_factor = EmissionFactorSerializer(read_only=True)
    source_type     = serializers.CharField(source="batch.source_type",   read_only=True)

    class Meta:
        model  = NormalizedEmission
        fields = [
            "id", "scope", "activity_type", "period_start", "period_end",
            "quantity_raw", "unit_raw", "quantity_normalized", "unit_normalized",
            "kg_co2e", "location", "cost_center", "source_label", "source_type",
            "is_edited", "emission_factor", "review_status", "analyst_note",
            "is_locked", "created_at", "updated_at",
        ]
