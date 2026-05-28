import uuid
from django.db import models


class EmissionFactor(models.Model):
    ACTIVITY_TYPES = [
        ("DIESEL_COMBUSTION",        "Diesel Combustion"),
        ("PETROL_COMBUSTION",        "Petrol Combustion"),
        ("NATURAL_GAS_COMBUSTION",   "Natural Gas Combustion"),
        ("HEATING_OIL_COMBUSTION",   "Heating Oil Combustion"),
        ("LPG_COMBUSTION",           "LPG Combustion"),
        ("BIODIESEL_COMBUSTION",     "Biodiesel Combustion"),
        ("FURNACE_OIL_COMBUSTION",   "Furnace Oil Combustion"),
        ("GRID_ELECTRICITY_UK",      "UK Grid Electricity"),
        ("GRID_ELECTRICITY_DE",      "German Grid Electricity"),
        ("GRID_ELECTRICITY_IN",      "Indian Grid Electricity"),
        ("GRID_ELECTRICITY_EU",      "EU Grid Electricity"),
        ("GRID_ELECTRICITY_UNKNOWN", "Unknown Grid Electricity"),
        ("FLIGHT_DOMESTIC",          "Flight Domestic"),
        ("FLIGHT_SHORT_HAUL",        "Flight Short Haul"),
        ("FLIGHT_LONG_HAUL",         "Flight Long Haul"),
        ("HOTEL_STAY",               "Hotel Stay"),
        ("GROUND_TRANSPORT_TAXI",    "Ground Transport Taxi"),
        ("GROUND_TRANSPORT_RENTAL",  "Ground Transport Car Rental"),
        ("GROUND_TRANSPORT_RAIL",    "Ground Transport Rail"),
    ]

    activity_type      = models.CharField(max_length=60, choices=ACTIVITY_TYPES)
    scope              = models.SmallIntegerField(choices=[(1, "Scope 1"), (2, "Scope 2"), (3, "Scope 3")])
    unit               = models.CharField(max_length=30)
    kg_co2e_per_unit   = models.DecimalField(max_digits=12, decimal_places=8)
    source_reference   = models.CharField(max_length=100)
    valid_from         = models.DateField()
    valid_to           = models.DateField(null=True, blank=True)
    is_active          = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.activity_type} / {self.unit} / {self.kg_co2e_per_unit} kg CO2e"

    class Meta:
        db_table       = "emissions_emissionfactor"
        unique_together = [("activity_type", "unit", "valid_from")]
        indexes = [models.Index(fields=["activity_type", "is_active"])]


class NormalizedEmission(models.Model):
    id                  = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant              = models.ForeignKey("tenants.Tenant", on_delete=models.CASCADE)
    raw_row             = models.OneToOneField("ingestion.RawRow", on_delete=models.PROTECT, related_name="emission")
    batch               = models.ForeignKey("ingestion.UploadBatch", on_delete=models.PROTECT)
    emission_factor     = models.ForeignKey(EmissionFactor, on_delete=models.PROTECT)
    scope               = models.SmallIntegerField(choices=[(1, "Scope 1"), (2, "Scope 2"), (3, "Scope 3")])
    activity_type       = models.CharField(max_length=60)
    period_start        = models.DateField()
    period_end          = models.DateField()
    quantity_raw        = models.DecimalField(max_digits=15, decimal_places=4)
    unit_raw            = models.CharField(max_length=30)
    quantity_normalized = models.DecimalField(max_digits=15, decimal_places=4)
    unit_normalized     = models.CharField(max_length=30)
    kg_co2e             = models.DecimalField(max_digits=15, decimal_places=6)
    location            = models.CharField(max_length=200, null=True, blank=True)
    cost_center         = models.CharField(max_length=100, null=True, blank=True)
    source_label        = models.CharField(max_length=200)
    is_edited           = models.BooleanField(default=False)
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.activity_type} / {self.kg_co2e} kg CO2e / {self.period_start}"

    class Meta:
        db_table = "emissions_normalizedemission"
        indexes  = [
            models.Index(fields=["tenant", "scope"]),
            models.Index(fields=["tenant", "period_start", "period_end"]),
            models.Index(fields=["tenant", "activity_type"]),
            models.Index(fields=["tenant", "batch"]),
        ]
