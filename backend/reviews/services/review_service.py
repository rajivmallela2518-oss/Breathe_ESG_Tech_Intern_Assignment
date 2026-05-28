from django.utils import timezone
from reviews.models import ReviewDecision
from audit.services import audit_service


def approve(emission, analyst, ip=None):
    decision = emission.review
    if decision.is_locked:
        raise ValueError("Row is locked and cannot be re-reviewed.")
    before = {"status": decision.status}
    decision.status = "APPROVED"
    decision.analyst = analyst
    decision.reviewed_at = timezone.now()
    decision.is_locked = True
    decision.save()
    audit_service.log(
        tenant=emission.tenant,
        action="ROW_APPROVED",
        obj=decision,
        actor=analyst,
        before=before,
        after={"status": "APPROVED"},
        ip=ip,
    )


def reject(emission, analyst, note, ip=None):
    if not note or not note.strip():
        raise ValueError("Analyst note is required when rejecting a row.")
    decision = emission.review
    if decision.is_locked:
        raise ValueError("Row is locked and cannot be re-reviewed.")
    before = {"status": decision.status}
    decision.status = "REJECTED"
    decision.analyst = analyst
    decision.analyst_note = note
    decision.reviewed_at = timezone.now()
    decision.save()
    audit_service.log(
        tenant=emission.tenant,
        action="ROW_REJECTED",
        obj=decision,
        actor=analyst,
        before=before,
        after={"status": "REJECTED", "note": note},
        ip=ip,
    )
