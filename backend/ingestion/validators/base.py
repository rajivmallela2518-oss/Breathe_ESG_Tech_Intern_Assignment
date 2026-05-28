from dataclasses import dataclass
from typing import Optional


@dataclass
class ValidationResult:
    flag_code: str
    severity: str          # ERROR | WARNING | INFO
    field_name: Optional[str]
    message: str


class BaseValidator:
    """
    Each validator subclass implements check(canonical, context) and returns
    a list of ValidationResult. Empty list means the row passed all rules.

    context carries batch-level state (e.g. checksums seen so far for
    duplicate detection, batch mean/std for outlier detection).
    """

    def check(self, canonical: dict, context: dict) -> list[ValidationResult]:
        raise NotImplementedError
