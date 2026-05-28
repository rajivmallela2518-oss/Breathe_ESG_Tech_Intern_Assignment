from decimal import Decimal
from django.utils import timezone
from emissions.models import NormalizedEmission, EmissionFactor
from emissions.services.unit_converter import convert, UnitConversionError
from emissions.services.scope_classifier import (
    classify_sap_row,
    classify_utility_row,
    get_scope,
)
from reviews.models import ReviewDecision
from audit.services import audit_service

CLASSIFIER_MAP = {
    "SAP_FUEL":            classify_sap_row,
    "UTILITY_ELECTRICITY": classify_utility_row,
    "CORPORATE_TRAVEL":    None,  # set in travel prompt
}


def normalize_batch(valid_raw_rows, source_type, tenant):
    """
    For each VALID raw row: classify → convert units → look up factor → compute kg CO2e
    → create NormalizedEmission → create ReviewDecision(PENDING).

    Rows that fail normalization (unknown activity type, missing factor, unit error)
    are marked FAILED and the reason is logged. They do not block other rows.
    """
    classifier = CLASSIFIER_MAP.get(source_type)

    for raw_row in valid_raw_rows:
        try:
            emission = _normalize_row(raw_row, source_type, classifier, tenant)
            ReviewDecision.objects.create(
                tenant=tenant,
                emission=emission,
                status="PENDING",
            )
            audit_service.log(
                tenant=tenant,
                action="ROW_NORMALIZED",
                obj=emission,
                after={"kg_co2e": str(emission.kg_co2e), "scope": emission.scope},
            )
        except Exception as exc:
            raw_row.status = "FAILED"
            raw_row.save(update_fields=["status"])
            # Surface the reason via a validation flag so analyst can see it
            from ingestion.models import ValidationFlag
            ValidationFlag.objects.create(
                tenant=tenant,
                raw_row=raw_row,
                flag_code="MISSING_MANDATORY_FIELD",
                severity="ERROR",
                field_name=None,
                message=f"Normalization failed: {exc}",
            )


def _normalize_row(raw_row, source_type, classifier, tenant):
    canonical = raw_row.canonical_data

    # 1. Classify activity type
    if classifier:
        activity_type = classifier(canonical)
    else:
        activity_type = canonical.get("activity_type", "")

    if not activity_type:
        raise ValueError("Could not determine activity_type from row data.")

    scope = get_scope(activity_type)

    # 2. Resolve reporting period
    if source_type == "SAP_FUEL":
        period_start = canonical.get("posting_date")
        period_end   = canonical.get("posting_date")
    else:
        period_start = canonical.get("period_start")
        period_end   = canonical.get("period_end")

    if not period_start or not period_end:
        raise ValueError("Cannot determine reporting period — date fields missing.")

    # 3. Convert units
    quantity_raw = canonical.get("quantity") or canonical.get("consumption_quantity")
    unit_raw     = canonical.get("unit") or canonical.get("consumption_unit", "")

    if quantity_raw is None:
        raise ValueError("Quantity field is None after parsing.")

    try:
        quantity_normalised, unit_normalised = convert(quantity_raw, unit_raw, activity_type)
    except UnitConversionError as e:
        raise ValueError(str(e))

    # 4. Look up emission factor (most recent active factor for this activity/unit)
    factor = EmissionFactor.objects.filter(
        activity_type=activity_type,
        unit=unit_normalised,
        is_active=True,
    ).order_by("-valid_from").first()

    if not factor:
        raise ValueError(
            f"No active emission factor for activity_type='{activity_type}', "
            f"unit='{unit_normalised}'. Load factor data via: "
            f"python manage.py loaddata emission_factors"
        )

    # 5. Compute kg CO2e
    kg_co2e = quantity_normalised * factor.kg_co2e_per_unit

    # 6. Build source label for audit trail
    if source_type == "SAP_FUEL":
        source_label = (
            f"SAP / {canonical.get('plant_code', '?')} / "
            f"{canonical.get('material_description', '?')}"
        )
    elif source_type == "UTILITY_ELECTRICITY":
        source_label = (
            f"Utility / {canonical.get('supplier', '?')} / "
            f"MPAN {canonical.get('meter_mpan', '?')}"
        )
    else:
        source_label = f"{source_type} / batch row {raw_row.row_number}"

    return NormalizedEmission.objects.create(
        tenant=tenant,
        raw_row=raw_row,
        batch=raw_row.batch,
        emission_factor=factor,
        scope=scope,
        activity_type=activity_type,
        period_start=period_start,
        period_end=period_end,
        quantity_raw=Decimal(str(quantity_raw)),
        unit_raw=unit_raw,
        quantity_normalized=quantity_normalised,
        unit_normalized=unit_normalised,
        kg_co2e=kg_co2e,
        location=canonical.get("plant_code") or canonical.get("site_reference") or "",
        cost_center=canonical.get("cost_center") or canonical.get("cost_centre") or "",
        source_label=source_label,
    )
