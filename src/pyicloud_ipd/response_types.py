"""ADT (Algebraic Data Type) definitions for response evaluation results."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Sequence

from requests import Response

if TYPE_CHECKING:
    from pyicloud_ipd.base import PyiCloudService
    from pyicloud_ipd.services.photos import PhotoLibrary, PhotosService


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


# Overall authentication result ADTs
@dataclass(frozen=True)
class AuthenticationSuccess:
    """Authentication completed successfully."""

    pass


@dataclass(frozen=True)
class AuthenticationSuccessWithService:
    """Authentication completed successfully with service instance."""

    service: "PyiCloudService"


@dataclass(frozen=True)
class AuthenticationFailed:
    """Authentication failed."""

    error: Exception


@dataclass(frozen=True)
class AuthRequires2SAWithService:
    """Authentication requires 2SA with service instance."""

    service: "PyiCloudService"
    account_name: str


@dataclass(frozen=True)
class AuthDomainMismatchError:
    """Domain mismatch error without service."""

    domain_to_use: str


# Union types for authentication results
ValidateTokenResult = AuthTokenValid | AuthTokenInvalid | AuthRequires2SA
AuthenticateSRPResult = AuthSRPSuccess | AuthSRPFailed | AuthRequires2SA
AuthenticateWithTokenResult = (
    AuthWithTokenSuccess | AuthWithTokenFailed | AuthRequires2SA | AuthDomainMismatch
)
# Service creation result - includes service in success/2SA cases
ServiceCreationResult = (
    AuthenticationSuccessWithService
    | AuthenticationFailed
    | AuthRequires2SAWithService
    | AuthDomainMismatchError
)
# Keep old AuthenticationResult for backward compatibility - used internally
AuthenticationResult = (
    AuthenticationSuccess | AuthenticationFailed | AuthRequires2SA | AuthDomainMismatch
)


# 2FA/2SA request result ADTs
@dataclass(frozen=True)
class TwoFactorAuthSuccess:
    """Two-factor authentication completed successfully."""

    pass


@dataclass(frozen=True)
class TwoFactorAuthFailed:
    """Two-factor authentication failed."""

    error: str


# Union type for 2FA/2SA results
TwoFactorAuthResult = TwoFactorAuthSuccess | TwoFactorAuthFailed


# Authenticator result ADTs
@dataclass(frozen=True)
class AuthenticatorSuccess:
    """Authentication completed successfully."""

    service: "PyiCloudService"


@dataclass(frozen=True)
class AuthenticatorConnectionError:
    """Connection error during authentication."""

    error: Exception


@dataclass(frozen=True)
class AuthenticatorMFAError:
    """MFA error during authentication."""

    error: str


@dataclass(frozen=True)
class AuthenticatorTwoSAExit:
    """2SA failed - need to exit with code 1."""

    pass


# Union type for authenticator results
AuthenticatorResult = (
    AuthenticatorSuccess
    | AuthenticatorConnectionError
    | AuthenticatorMFAError
    | AuthenticatorTwoSAExit
)


# PhotoLibrary initialization ADTs
@dataclass(frozen=True)
class PhotoLibraryInitSuccess:
    """Photo library initialized successfully."""

    library: "PhotoLibrary"


@dataclass(frozen=True)
class PhotoLibraryNotFinishedIndexing:
    """Photo library has not finished indexing."""

    pass


@dataclass(frozen=True)
class PhotoLibraryInitFailed:
    """Photo library initialization failed."""

    error: Exception


# Union type for PhotoLibrary initialization results
PhotoLibraryInitResult = (
    PhotoLibraryInitSuccess | PhotoLibraryNotFinishedIndexing | PhotoLibraryInitFailed
)


# PhotosService initialization ADTs
@dataclass(frozen=True)
class PhotosServiceInitSuccess:
    """Photos service initialized successfully."""

    service: "PhotosService"


# Union type for PhotosService initialization results
# Reuses PhotoLibraryNotFinishedIndexing and PhotoLibraryInitFailed since they're the same
PhotosServiceInitResult = (
    PhotosServiceInitSuccess | PhotoLibraryNotFinishedIndexing | PhotoLibraryInitFailed
)


# Library fetching ADTs
@dataclass(frozen=True)
class LibrariesFetchSuccess:
    """Libraries fetched successfully."""

    libraries: Dict[str, "PhotoLibrary"]
    skipped: Dict[str, str]  # zone_name -> reason for skipping


@dataclass(frozen=True)
class LibrariesFetchFailed:
    """Failed to fetch libraries list."""

    error: Exception


# Union type for library fetching results
LibrariesFetchResult = LibrariesFetchSuccess | LibrariesFetchFailed


# Folder fetching ADTs
@dataclass(frozen=True)
class FoldersFetchSuccess:
    """Folders fetched successfully."""

    folders: Sequence[Dict[str, Any]]


@dataclass(frozen=True)
class FoldersFetchFailed:
    """Failed to fetch folders list."""

    error: Exception


# Union type for folder fetching results
FoldersFetchResult = FoldersFetchSuccess | FoldersFetchFailed


# Album length ADTs
@dataclass(frozen=True)
class AlbumLengthSuccess:
    """Album length retrieved successfully."""

    count: int


@dataclass(frozen=True)
class AlbumLengthFailed:
    """Failed to retrieve album length."""

    error: Exception


# Union type for album length results
AlbumLengthResult = AlbumLengthSuccess | AlbumLengthFailed


# Download asset ADTs
@dataclass(frozen=True)
class DownloadSuccess:
    """Asset downloaded successfully."""

    response: Response


@dataclass(frozen=True)
class DownloadFailed:
    """Failed to download asset."""

    error: Exception


# Union type for download results
DownloadResult = DownloadSuccess | DownloadFailed
