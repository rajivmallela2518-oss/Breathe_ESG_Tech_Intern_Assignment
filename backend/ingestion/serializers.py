from rest_framework import serializers
from .models import UploadBatch, RawRow, ValidationFlag


class ValidationFlagSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ValidationFlag
        fields = ["id", "flag_code", "severity", "field_name", "message"]


class RawRowSerializer(serializers.ModelSerializer):
    flags = ValidationFlagSerializer(many=True, read_only=True)

    class Meta:
        model  = RawRow
        fields = ["id", "row_number", "source_type", "raw_data", "status", "flags", "created_at"]


class UploadBatchSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source="uploaded_by.full_name", read_only=True)

    class Meta:
        model  = UploadBatch
        fields = [
            "id", "source_type", "original_filename", "status",
            "total_rows", "valid_rows", "flagged_rows", "failed_rows",
            "uploaded_by_name", "created_at", "completed_at", "error_message",
        ]


class UploadResponseSerializer(serializers.Serializer):
    batch_id    = serializers.UUIDField()
    total_rows  = serializers.IntegerField()
    valid_rows  = serializers.IntegerField()
    flagged_rows = serializers.IntegerField()
    failed_rows = serializers.IntegerField()
    status      = serializers.CharField()
