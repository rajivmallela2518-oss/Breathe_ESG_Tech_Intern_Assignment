from rest_framework import serializers
from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.full_name", default=None)

    class Meta:
        model  = AuditLog
        fields = [
            "id", "action", "actor_name", "object_repr",
            "before_state", "after_state", "timestamp", "ip_address",
        ]
