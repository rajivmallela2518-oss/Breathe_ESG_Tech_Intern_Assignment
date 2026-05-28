from django.contrib.contenttypes.models import ContentType
from audit.models import AuditLog


def log(tenant, action, obj, actor=None, before=None, after=None, ip=None):
    """
    Single entry point for all audit events across the system.

    Called by ingestion, emissions, and reviews services — never called
    from views directly. This keeps audit writes inside the service layer
    where they're co-located with the state changes they record.
    """
    AuditLog.objects.create(
        tenant=tenant,
        actor=actor,
        action=action,
        content_type=ContentType.objects.get_for_model(obj),
        object_id=obj.pk,
        object_repr=str(obj),
        before_state=before,
        after_state=after,
        ip_address=ip,
    )
