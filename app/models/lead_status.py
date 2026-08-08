from dataclasses import dataclass


@dataclass(frozen=True)
class LeadStatusStep:
    code: int
    value: str
    label: str


LEAD_STATUS_PIPELINE: list[LeadStatusStep] = [
    LeadStatusStep(0, "new", "Pendiente de contacto"),
    LeadStatusStep(1, "contacted", "Contacto realizado"),
    LeadStatusStep(2, "responded", "Respondió"),
    LeadStatusStep(3, "follow_up", "En seguimiento"),
    LeadStatusStep(4, "closed", "Cerrado"),
    LeadStatusStep(5, "discarded", "Descartado"),
]

_STATUS_BY_VALUE = {step.value: step for step in LEAD_STATUS_PIPELINE}
_STATUS_BY_CODE = {step.code: step for step in LEAD_STATUS_PIPELINE}


def status_to_code(status: str) -> int:
    return _STATUS_BY_VALUE.get(status, _STATUS_BY_VALUE["new"]).code


def status_label(status: str) -> str:
    return _STATUS_BY_VALUE.get(status, _STATUS_BY_VALUE["new"]).label


def code_to_status(code: int) -> str:
    return _STATUS_BY_CODE.get(code, _STATUS_BY_CODE[0]).value
