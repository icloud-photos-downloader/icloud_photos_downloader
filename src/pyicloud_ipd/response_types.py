"""ADT (Algebraic Data Type) definitions for response evaluation results."""

from dataclasses import dataclass
from typing import Any, Dict

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


@dataclass(frozen=True)
class ResponseServiceUnavailable:
    """Response indicates service is unavailable (503)."""

    reason: str


# Union type for all possible response evaluation results
ResponseEvaluation = (
    ResponseSuccess
    | Response2SARequired
    | ResponseServiceNotActivated
    | ResponseAPIError
    | ResponseServiceUnavailable
)


# Authentication-specific ADTs
@dataclass(frozen=True)
class AuthTokenValid:
    """Token validation successful."""

    data: Dict[str, Any]


@dataclass(frozen=True)
class AuthTokenInvalid:
    """Token validation failed."""

    error: Exception


@dataclass(frozen=True)
class AuthSRPSuccess:
    """SRP authentication successful."""

    pass


@dataclass(frozen=True)
class AuthSRPFailed:
    """SRP authentication failed."""

    error: Exception


@dataclass(frozen=True)
class AuthWithTokenSuccess:
    """Token authentication successful."""

    data: Dict[str, Any]


@dataclass(frozen=True)
class AuthWithTokenFailed:
    """Token authentication failed."""

    error: Exception


@dataclass(frozen=True)
class AuthRequires2SA:
    """Authentication requires 2SA."""

    account_name: str


@dataclass(frozen=True)
class AuthDomainMismatch:
    """Domain mismatch error."""

    domain_to_use: str


# Union types for authentication results
ValidateTokenResult = AuthTokenValid | AuthTokenInvalid | AuthRequires2SA
AuthenticateSRPResult = AuthSRPSuccess | AuthSRPFailed | AuthRequires2SA
AuthenticateWithTokenResult = (
    AuthWithTokenSuccess | AuthWithTokenFailed | AuthRequires2SA | AuthDomainMismatch
)
