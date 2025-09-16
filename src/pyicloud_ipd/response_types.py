"""ADT (Algebraic Data Type) definitions for response evaluation results."""

from dataclasses import dataclass

from requests import Response


@dataclass(frozen=True)
class ResponseSuccess:
    """Successful response evaluation result."""

    response: Response


@dataclass(frozen=True)
class Response2SARequired:
    """Response indicates 2SA is required."""

    account_name: str


@dataclass(frozen=True)
class ResponseServiceNotActivated:
    """Response indicates service is not activated."""

    reason: str
    code: str


@dataclass(frozen=True)
class ResponseAPIError:
    """Response indicates an API error."""

    reason: str
    code: str


# Union type for all possible response evaluation results
ResponseEvaluation = (
    ResponseSuccess | Response2SARequired | ResponseServiceNotActivated | ResponseAPIError
)
