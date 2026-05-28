"""
Converts incoming unit strings to the canonical unit for each activity category.

Design principle: every conversion is explicit and named. No generic "convert
any unit to any other unit" function — only conversions we have actually
encountered in real source data. This makes the conversion logic auditable
and prevents silent errors from unexpected unit strings.
"""

from decimal import Decimal


class UnitConversionError(Exception):
    pass


# (incoming_unit_normalised, activity_category) → (factor, canonical_unit)
# factor: multiply incoming quantity by this to get canonical quantity
# activity_category: broad grouping to allow the same unit in different contexts

CONVERSION_TABLE = {
    # -------- Liquid fuels → litres --------
    ("l",      "fuel"): (Decimal("1"),         "litre"),
    ("liter",  "fuel"): (Decimal("1"),         "litre"),
    ("litre",  "fuel"): (Decimal("1"),         "litre"),
    ("liters", "fuel"): (Decimal("1"),         "litre"),
    ("litres", "fuel"): (Decimal("1"),         "litre"),
    ("gal",    "fuel"): (Decimal("3.78541"),   "litre"),  # US gallon
    ("usgal",  "fuel"): (Decimal("3.78541"),   "litre"),
    ("ukgal",  "fuel"): (Decimal("4.54609"),   "litre"),  # Imperial gallon
    ("m3",     "fuel"): (Decimal("1000"),      "litre"),  # cubic metres of liquid

    # -------- Solid/mass fuels → kg --------
    ("kg",     "mass_fuel"): (Decimal("1"),    "kg"),
    ("t",      "mass_fuel"): (Decimal("1000"), "kg"),
    ("mt",     "mass_fuel"): (Decimal("1000"), "kg"),
    ("lb",     "mass_fuel"): (Decimal("0.453592"), "kg"),

    # -------- Gas fuels → m³ --------
    ("m3",     "gas"): (Decimal("1"),          "m3"),
    ("m³",     "gas"): (Decimal("1"),          "m3"),
    ("scm",    "gas"): (Decimal("1"),          "m3"),  # standard cubic metre
    ("ft3",    "gas"): (Decimal("0.0283168"),  "m3"),  # cubic feet

    # -------- Electricity → kWh --------
    ("kwh",    "electricity"): (Decimal("1"),          "kWh"),
    ("mwh",    "electricity"): (Decimal("1000"),       "kWh"),
    ("gwh",    "electricity"): (Decimal("1000000"),    "kWh"),

    # -------- Travel distance → km --------
    ("km",     "distance"): (Decimal("1"),       "km"),
    ("miles",  "distance"): (Decimal("1.60934"), "km"),
    ("mi",     "distance"): (Decimal("1.60934"), "km"),

    # -------- Hotel stays → room-nights (identity conversion) --------
    ("room_night", "hotel"): (Decimal("1"), "room_night"),
}

# Activity types → conversion category
ACTIVITY_TO_CATEGORY = {
    "DIESEL_COMBUSTION":        "fuel",
    "PETROL_COMBUSTION":        "fuel",
    "BIODIESEL_COMBUSTION":     "fuel",
    "HVO_COMBUSTION":           "fuel",
    "FURNACE_OIL_COMBUSTION":   "fuel",
    "HEATING_OIL_COMBUSTION":   "mass_fuel",
    "LPG_COMBUSTION":           "mass_fuel",
    "NATURAL_GAS_COMBUSTION":   "gas",
    "GRID_ELECTRICITY_UK":      "electricity",
    "GRID_ELECTRICITY_DE":      "electricity",
    "GRID_ELECTRICITY_IN":      "electricity",
    "GRID_ELECTRICITY_EU":      "electricity",
    "GRID_ELECTRICITY_UNKNOWN": "electricity",
    "FLIGHT_DOMESTIC":          "distance",
    "FLIGHT_SHORT_HAUL":        "distance",
    "FLIGHT_LONG_HAUL":         "distance",
    "GROUND_TRANSPORT_TAXI":    "distance",
    "GROUND_TRANSPORT_RENTAL":  "distance",
    "GROUND_TRANSPORT_RAIL":    "distance",
    "HOTEL_STAY":               "hotel",
}


def convert(quantity: float, unit: str, activity_type: str) -> tuple[Decimal, str]:
    """
    Convert (quantity, unit) to the canonical (quantity, unit) for the given activity_type.

    Returns (normalised_quantity, canonical_unit).
    Raises UnitConversionError if the combination is unknown.
    """
    category = ACTIVITY_TO_CATEGORY.get(activity_type)
    if not category:
        raise UnitConversionError(
            f"Unknown activity_type '{activity_type}' — cannot determine unit category."
        )

    unit_key = unit.strip().lower()
    key = (unit_key, category)

    if key not in CONVERSION_TABLE:
        raise UnitConversionError(
            f"No conversion rule for unit '{unit}' in category '{category}' "
            f"(activity: {activity_type}). Add it to CONVERSION_TABLE."
        )

    factor, canonical_unit = CONVERSION_TABLE[key]
    return Decimal(str(quantity)) * factor, canonical_unit
