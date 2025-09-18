"""ADT (Algebraic Data Type) definitions for response evaluation results."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Sequence

from requests import Response

if TYPE_CHECKING:
    from pyicloud_ipd.base import PyiCloudService
    from pyicloud_ipd.services.photos import PhotoAlbum, PhotoAsset, PhotoLibrary, PhotosService
    from pyicloud_ipd.sms import TrustedDevice


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
class AuthSRPSuccess:
    """SRP authentication successful."""

    pass


@dataclass(frozen=True)
class AuthWithTokenSuccess:
    """Token authentication successful."""

    data: Dict[str, Any]


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


# Union types for authentication results - reuse response evaluation ADTs
ValidateTokenResult = (
    AuthTokenValid
    | Response2SARequired
    | ResponseServiceNotActivated
    | ResponseAPIError
    | ResponseServiceUnavailable
    | AuthRequires2SA
)
AuthenticateSRPResult = (
    AuthSRPSuccess
    | Response2SARequired
    | ResponseServiceNotActivated
    | ResponseAPIError
    | ResponseServiceUnavailable
    | AuthRequires2SA
)
# AuthenticateWithTokenResult now reuses the response evaluation ADTs directly
AuthenticateWithTokenResult = (
    AuthWithTokenSuccess
    | ResponseServiceNotActivated
    | ResponseAPIError
    | ResponseServiceUnavailable
    | AuthRequires2SA
    | AuthDomainMismatch
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


# Union type for PhotoLibrary initialization results - reuses response evaluation ADTs
PhotoLibraryInitResult = (
    PhotoLibraryInitSuccess
    | PhotoLibraryNotFinishedIndexing
    | Response2SARequired
    | ResponseServiceNotActivated
    | ResponseAPIError
    | ResponseServiceUnavailable
)


# PhotosService initialization ADTs
@dataclass(frozen=True)
class PhotosServiceInitSuccess:
    """Photos service initialized successfully."""

    service: "PhotosService"


# Union type for PhotosService initialization results - reuses response evaluation ADTs
PhotosServiceInitResult = (
    PhotosServiceInitSuccess
    | PhotoLibraryNotFinishedIndexing
    | Response2SARequired
    | ResponseServiceNotActivated
    | ResponseAPIError
    | ResponseServiceUnavailable
)


# PhotosService access ADTs (for PyiCloudService.photos property)
@dataclass(frozen=True)
class PhotosServiceAccessSuccess:
    """Photos service accessed successfully."""

    service: "PhotosService"


# Union type for PhotosService access results - reuses response evaluation ADTs
PhotosServiceAccessResult = (
    PhotosServiceAccessSuccess
    | PhotoLibraryNotFinishedIndexing
    | Response2SARequired
    | ResponseServiceNotActivated
    | ResponseAPIError
    | ResponseServiceUnavailable
)


# Library fetching ADTs
@dataclass(frozen=True)
class LibrariesFetchSuccess:
    """Libraries fetched successfully."""

    libraries: Dict[str, "PhotoLibrary"]
    skipped: Dict[str, str]  # zone_name -> reason for skipping


# Union type for library fetching results - reuses response evaluation ADTs
LibrariesFetchResult = (
    LibrariesFetchSuccess
    | Response2SARequired
    | ResponseServiceNotActivated
    | ResponseAPIError
    | ResponseServiceUnavailable
)


# Folder fetching ADTs
@dataclass(frozen=True)
class FoldersFetchSuccess:
    """Folders fetched successfully."""

    folders: Sequence[Dict[str, Any]]


# Union type for folder fetching results - reuses response evaluation ADTs
FoldersFetchResult = (
    FoldersFetchSuccess
    | Response2SARequired
    | ResponseServiceNotActivated
    | ResponseAPIError
    | ResponseServiceUnavailable
)


# Album length ADTs
@dataclass(frozen=True)
class AlbumLengthSuccess:
    """Album length retrieved successfully."""

    count: int


# Union type for album length results - reuses response evaluation ADTs
AlbumLengthResult = (
    AlbumLengthSuccess
    | Response2SARequired
    | ResponseServiceNotActivated
    | ResponseAPIError
    | ResponseServiceUnavailable
)


# Download asset ADTs
@dataclass(frozen=True)
class DownloadSuccess:
    """Asset downloaded successfully."""

    response: Response


# Union type for download results - reuses response evaluation ADTs
DownloadResult = (
    DownloadSuccess
    | Response2SARequired
    | ResponseServiceNotActivated
    | ResponseAPIError
    | ResponseServiceUnavailable
)


# Photos request ADTs
@dataclass(frozen=True)
class PhotosRequestSuccess:
    """Photos request succeeded."""

    response: Response


# Union type for photos request results - reuses response evaluation ADTs
PhotosRequestResult = (
    PhotosRequestSuccess
    | Response2SARequired
    | ResponseServiceNotActivated
    | ResponseAPIError
    | ResponseServiceUnavailable
)


# Photo iteration ADTs
@dataclass(frozen=True)
class PhotoIterationSuccess:
    """Successfully retrieved a photo asset."""

    asset: "PhotoAsset"


@dataclass(frozen=True)
class PhotoIterationComplete:
    """No more photos to iterate."""

    pass


# Union type for photo iteration results - reuses response evaluation ADTs
PhotoIterationResult = (
    PhotoIterationSuccess
    | PhotoIterationComplete
    | Response2SARequired
    | ResponseServiceNotActivated
    | ResponseAPIError
    | ResponseServiceUnavailable
)


# Autodelete ADTs
@dataclass(frozen=True)
class AutodeleteSuccess:
    """Autodelete completed successfully."""

    pass


# Union type for autodelete results - reuses response evaluation ADTs
AutodeleteResult = (
    AutodeleteSuccess
    | Response2SARequired
    | ResponseServiceNotActivated
    | ResponseAPIError
    | ResponseServiceUnavailable
)


# Albums fetch ADTs (for PhotoLibrary.albums property)
@dataclass(frozen=True)
class AlbumsFetchSuccess:
    """Albums fetched successfully."""

    albums: Dict[str, "PhotoAlbum"]


# Union type for albums fetch results - reuses response evaluation ADTs
AlbumsFetchResult = (
    AlbumsFetchSuccess
    | Response2SARequired
    | ResponseServiceNotActivated
    | ResponseAPIError
    | ResponseServiceUnavailable
)


# Libraries access ADTs (for PhotosService.private_libraries/shared_libraries properties)
@dataclass(frozen=True)
class LibrariesAccessSuccess:
    """Libraries accessed successfully."""

    libraries: Dict[str, "PhotoLibrary"]


# Union type for libraries access results - reuses response evaluation ADTs
LibrariesAccessResult = (
    LibrariesAccessSuccess
    | Response2SARequired
    | ResponseServiceNotActivated
    | ResponseAPIError
    | ResponseServiceUnavailable
)


# Download media ADTs (for download.py)
@dataclass(frozen=True)
class DownloadMediaSuccess:
    """Media downloaded successfully."""

    pass


@dataclass(frozen=True)
class DownloadMediaSkipped:
    """Media download skipped (file already exists or was filtered)."""

    pass


# Union type for download media results - reuses response evaluation ADTs
DownloadMediaResult = (
    DownloadMediaSuccess
    | DownloadMediaSkipped
    | Response2SARequired
    | ResponseServiceNotActivated
    | ResponseAPIError
    | ResponseServiceUnavailable
)


# Delete photo ADTs
@dataclass(frozen=True)
class DeletePhotoSuccess:
    """Photo deleted successfully."""

    pass


# Union type for delete photo results - reuses response evaluation ADTs
DeletePhotoResult = (
    DeletePhotoSuccess
    | Response2SARequired
    | ResponseServiceNotActivated
    | ResponseAPIError
    | ResponseServiceUnavailable
)


# Trusted devices ADTs
@dataclass(frozen=True)
class TrustedDevicesSuccess:
    """Trusted devices retrieved successfully."""

    devices: Sequence[Dict[str, Any]]


# Union type for trusted devices results - reuses response evaluation ADTs
TrustedDevicesResult = (
    TrustedDevicesSuccess
    | Response2SARequired
    | ResponseServiceNotActivated
    | ResponseAPIError
    | ResponseServiceUnavailable
)


# Trusted phone numbers ADTs
@dataclass(frozen=True)
class TrustedPhoneNumbersSuccess:
    """Trusted phone numbers retrieved successfully."""

    devices: Sequence["TrustedDevice"]


# Union type for trusted phone numbers results - reuses response evaluation ADTs
TrustedPhoneNumbersResult = (
    TrustedPhoneNumbersSuccess
    | Response2SARequired
    | ResponseServiceNotActivated
    | ResponseAPIError
    | ResponseServiceUnavailable
)


# Send verification code ADTs
@dataclass(frozen=True)
class SendVerificationCodeSuccess:
    """Verification code sent successfully."""

    success: bool


# Union type for send verification code results - reuses response evaluation ADTs
SendVerificationCodeResult = (
    SendVerificationCodeSuccess
    | Response2SARequired
    | ResponseServiceNotActivated
    | ResponseAPIError
    | ResponseServiceUnavailable
)


# Send 2FA code SMS ADTs
@dataclass(frozen=True)
class Send2FACodeSMSSuccess:
    """2FA code SMS sent successfully."""

    success: bool


# Union type for send 2FA code SMS results - reuses response evaluation ADTs
Send2FACodeSMSResult = (
    Send2FACodeSMSSuccess
    | Response2SARequired
    | ResponseServiceNotActivated
    | ResponseAPIError
    | ResponseServiceUnavailable
)


# Validate verification code ADTs
@dataclass(frozen=True)
class ValidateVerificationCodeSuccess:
    """Verification code validated successfully."""

    success: bool


@dataclass(frozen=True)
class ValidateVerificationCodeFailed:
    """Verification code validation failed."""

    pass


# Union type for validate verification code results - reuses response evaluation ADTs
ValidateVerificationCodeResult = (
    ValidateVerificationCodeSuccess
    | ValidateVerificationCodeFailed
    | Response2SARequired
    | ResponseServiceNotActivated
    | ResponseAPIError
    | ResponseServiceUnavailable
    | AuthDomainMismatch
)


# Validate 2FA code SMS ADTs
@dataclass(frozen=True)
class Validate2FACodeSMSSuccess:
    """2FA code SMS validated successfully."""

    success: bool


@dataclass(frozen=True)
class Validate2FACodeSMSFailed:
    """2FA code SMS validation failed."""

    pass


# Union type for validate 2FA code SMS results - reuses response evaluation ADTs
Validate2FACodeSMSResult = (
    Validate2FACodeSMSSuccess
    | Validate2FACodeSMSFailed
    | Response2SARequired
    | ResponseServiceNotActivated
    | ResponseAPIError
    | ResponseServiceUnavailable
    | AuthDomainMismatch
)


# Validate 2FA code ADTs
@dataclass(frozen=True)
class Validate2FACodeSuccess:
    """2FA code validated successfully."""

    success: bool


@dataclass(frozen=True)
class Validate2FACodeFailed:
    """2FA code validation failed."""

    pass


# Union type for validate 2FA code results - reuses response evaluation ADTs
Validate2FACodeResult = (
    Validate2FACodeSuccess
    | Validate2FACodeFailed
    | Response2SARequired
    | ResponseServiceNotActivated
    | ResponseAPIError
    | ResponseServiceUnavailable
    | AuthDomainMismatch
)


# Trust session ADTs
@dataclass(frozen=True)
class TrustSessionSuccess:
    """Session trusted successfully."""

    success: bool


@dataclass(frozen=True)
class TrustSessionFailed:
    """Session trust failed."""

    pass


# Union type for trust session results - reuses response evaluation ADTs
TrustSessionResult = (
    TrustSessionSuccess
    | TrustSessionFailed
    | Response2SARequired
    | ResponseServiceNotActivated
    | ResponseAPIError
    | ResponseServiceUnavailable
    | AuthDomainMismatch
)


# Get webservice URL ADTs
@dataclass(frozen=True)
class WebserviceURLSuccess:
    """Webservice URL retrieved successfully."""

    url: str


@dataclass(frozen=True)
class WebserviceNotAvailable:
    """Webservice not available."""

    service_key: str


# Union type for get webservice URL results
WebserviceURLResult = WebserviceURLSuccess | WebserviceNotAvailable
