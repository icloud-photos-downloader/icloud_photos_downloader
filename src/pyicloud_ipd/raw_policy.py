from enum import Enum


class RawTreatmentPolicy(Enum):
    AS_IS = "as-is"
    AS_ORIGINAL = "as-original"
    AS_ALTERNATIVE = "as-alternative"

    def __str__(self) -> str:
        return self.name

