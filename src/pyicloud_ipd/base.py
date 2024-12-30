import sys
from typing import Any, Callable, Dict, NamedTuple, Optional, Sequence
import typing
from uuid import uuid1
import json
import logging
from tempfile import gettempdir
from os import path, mkdir
from re import match
import http.cookiejar as cookielib
import getpass
import srp
import base64
import hashlib

from requests import PreparedRequest, Request, Response

from pyicloud_ipd.exceptions import (
    PyiCloudConnectionException,
    PyiCloudFailedLoginException,
    PyiCloudAPIResponseException,
    PyiCloudServiceNotActivatedException,
)
from pyicloud_ipd.file_match import FileMatchPolicy
from pyicloud_ipd.raw_policy import RawTreatmentPolicy
from pyicloud_ipd.services.findmyiphone import AppleDevice, FindMyiPhoneServiceManager
from pyicloud_ipd.services.calendar import CalendarService
from pyicloud_ipd.services.ubiquity import UbiquityService
from pyicloud_ipd.services.contacts import ContactsService
from pyicloud_ipd.services.reminders import RemindersService
from pyicloud_ipd.services.photos import PhotosService
from pyicloud_ipd.services.account import AccountService
from pyicloud_ipd.session import PyiCloudPasswordFilter, PyiCloudSession
from pyicloud_ipd.sms import AuthenticatedSession, TrustedDevice, build_send_sms_code_request, build_trusted_phone_numbers_request, build_verify_sms_code_request, parse_trusted_phone_numbers_response


LOGGER = logging.getLogger(__name__)

HEADER_DATA = {
    "X-Apple-ID-Account-Country": "account_country",
    "X-Apple-ID-Session-Id": "session_id",
    "X-Apple-Session-Token": "session_token",
    "X-Apple-TwoSV-Trust-Token": "trust_token",
    "X-Apple-TwoSV-Trust-Eligible": "trust_eligible",
    "X-Apple-I-Rscd": "apple_rscd",
    "X-Apple-I-Ercd": "apple_ercd",
    "scnt": "scnt",
}

class TrustedPhoneContextProvider(NamedTuple):
    domain: str
    oauth_session: AuthenticatedSession



class PyiCloudService:
    """
    A base authentication class for the iCloud service. Handles the
    authentication required to access iCloud services.

    Usage:
        from pyicloud_ipd import PyiCloudService
        pyicloud = PyiCloudService('username@apple.com', 'password')
        pyicloud_ipd.iphone.location()
    """

    def __init__(
        self, 
        filename_cleaner: Callable[[str], str],
        lp_filename_generator: Callable[[str], str],
        domain:str, 
        raw_policy: RawTreatmentPolicy,
        file_match_policy: FileMatchPolicy,
        apple_id: str, password:str, cookie_directory:Optional[str]=None, verify:bool=True,
        client_id:Optional[str]=None, with_family:bool=True,
    ):
        self.filename_cleaner = filename_cleaner
        self.lp_filename_generator = lp_filename_generator
        self.raw_policy = raw_policy
        self.file_match_policy = file_match_policy
        self.user: Dict[str, Any] = {"accountName": apple_id, "password": password}
        self.data: Dict[str, Any] = {} 
        self.params: Dict[str, Any] = {}
        self.client_id: str = client_id or ("auth-%s" % str(uuid1()).lower())
        self.with_family = with_family

        self.password_filter = PyiCloudPasswordFilter(password)
        LOGGER.addFilter(self.password_filter)

        if (domain == 'com'):
            self.AUTH_ENDPOINT = "https://idmsa.apple.com/appleauth/auth"
            self.HOME_ENDPOINT = "https://www.icloud.com"
            self.SETUP_ENDPOINT = "https://setup.icloud.com/setup/ws/1"
        elif (domain == 'cn'):
            self.AUTH_ENDPOINT = "https://idmsa.apple.com.cn/appleauth/auth"
            self.HOME_ENDPOINT = "https://www.icloud.com.cn"
            self.SETUP_ENDPOINT = "https://setup.icloud.com.cn/setup/ws/1"
        else:
            raise NotImplementedError(f"Domain '{domain}' is not supported yet")

        self.domain = domain

        if cookie_directory:
            self._cookie_directory = path.expanduser(
                path.normpath(cookie_directory)
            )
            if not path.exists(self._cookie_directory):
                mkdir(self._cookie_directory, 0o700)
        else:
            topdir = path.join(gettempdir(), "pyicloud")
            self._cookie_directory = path.join(topdir, getpass.getuser())
            if not path.exists(topdir):
                mkdir(topdir, 0o777)
            if not path.exists(self._cookie_directory):
                mkdir(self._cookie_directory, 0o700)

        LOGGER.debug("Using session file %s", self.session_path)

        self.session_data = {}
        try:
            with open(self.session_path, encoding="utf-8") as session_f:
                self.session_data = json.load(session_f)
        except:  
            LOGGER.info("Session file does not exist")
        session_client_id: Optional[str] = self.session_data.get("client_id")
        if session_client_id:
            self.client_id = session_client_id
        else:
            self.session_data.update({"client_id": self.client_id})

        self.session:PyiCloudSession = PyiCloudSession(self)
        self.session.verify = verify
        self.session.headers.update({
            'Origin': self.HOME_ENDPOINT,
            'Referer': '%s/' % self.HOME_ENDPOINT,
            'User-Agent': 'Opera/9.52 (X11; Linux i686; U; en)'
        })

        cookiejar_path = self.cookiejar_path
        self.session.cookies = cookielib.LWPCookieJar(filename=cookiejar_path) # type: ignore[assignment]
        if path.exists(cookiejar_path):
            try:
                self.session.cookies.load(ignore_discard=True, ignore_expires=True) # type: ignore[attr-defined]
                LOGGER.debug("Read cookies from %s", cookiejar_path)
            except:
                # Most likely a pickled cookiejar from earlier versions.
                # The cookiejar will get replaced with a valid one after
                # successful authentication.
                LOGGER.warning("Failed to read cookiejar %s", cookiejar_path)

        # Unsure if this is still needed
        self.params = {
            'clientBuildNumber': '17DHotfix5',
            'clientMasteringNumber': '17DHotfix5',
            'ckjsBuildVersion': '17DProjectDev77',
            'ckjsVersion': '2.0.5',
            'clientId': self.client_id,
        }

        self.authenticate()

        self._photos: Optional[PhotosService] = None

    def authenticate(self, force_refresh:bool=False, service:Optional[Any]=None) -> None:
        """
        Handles authentication, and persists cookies so that
        subsequent logins will not cause additional e-mails from Apple.
        """

        login_successful = False
        if self.session_data.get("session_token") and not force_refresh:
            LOGGER.debug("Checking session token validity")
            try:
                self.data = self._validate_token()
                login_successful = True
            except PyiCloudAPIResponseException:
                LOGGER.debug("Invalid authentication token, will log in from scratch.")

        if not login_successful and service is not None:
            app = self.data["apps"][service]
            if "canLaunchWithOneFactor" in app and app["canLaunchWithOneFactor"]:
                LOGGER.debug(
                    "Authenticating as %s for %s", self.user["accountName"], service
                )
                try:
                    self._authenticate_with_credentials_service(service)
                    login_successful = True
                except Exception:
                    LOGGER.debug(
                        "Could not log into service. Attempting brand new login."
                    )

        if not login_successful:
            LOGGER.debug("Authenticating as %s", self.user["accountName"])
            try:
                self._authenticate_srp()
            except PyiCloudFailedLoginException as error:
                LOGGER.error("Failed to login with srp, falling back to old raw password authentication. Error: %s", error)
                try:
                    self._authenticate_raw_password()
                except PyiCloudFailedLoginException as error:
                    LOGGER.error("Failed to login with raw password. Error: %s", error)
                    raise error

            self._authenticate_with_token()

        # Is this needed?
        self.params.update({'dsid': self.data['dsInfo']['dsid']})

        self._webservices = self.data["webservices"]

        LOGGER.info("Authentication completed successfully")
        LOGGER.debug(self.params)

    def _authenticate_with_token(self) -> None:
        """Authenticate using session token."""
        data = {
            "accountCountryCode": self.session_data.get("account_country"),
            "dsWebAuthToken": self.session_data.get("session_token"),
            "extended_login": True,
            "trustToken": self.session_data.get("trust_token", ""),
        }

        try:
            req = self.session.post(
                "%s/accountLogin" % self.SETUP_ENDPOINT, data=json.dumps(data)
            )
            self.data = req.json()
        except PyiCloudAPIResponseException as error:
            msg = "Invalid authentication token."
            raise PyiCloudFailedLoginException(msg, error) from error

        # {'domainToUse': 'iCloud.com'}
        domain_to_use = self.data.get('domainToUse')
        if domain_to_use != None:
            msg = f'Apple insists on using {domain_to_use} for your request. Please use --domain parameter'
            raise PyiCloudConnectionException(msg)

    def _authenticate_with_credentials_service(self, service: str) -> None:
        """Authenticate to a specific service using credentials."""
        data = {
            "appName": service,
            "apple_id": self.user["accountName"],
            "password": self.user["password"],
        }

        try:
            self.session.post(
                "%s/accountLogin" % self.SETUP_ENDPOINT, data=json.dumps(data)
            )

            self.data = self._validate_token()
        except PyiCloudAPIResponseException as error:
            msg = "Invalid email/password combination."
            raise PyiCloudFailedLoginException(msg, error) from error

    def _authenticate_srp(self) -> None:
        class SrpPassword():
            # srp uses the encoded password at process_challenge(), thus set_encrypt_info() should be called before that
            def __init__(self, password: str):
                self.pwd = password

            def set_encrypt_info(self, protocol: str, salt: bytes, iterations: int) -> None:
                self.protocol = protocol
                self.salt = salt
                self.iterations = iterations

            def encode(self) -> bytes:
                password_hash = hashlib.sha256(self.pwd.encode())
                password_digest = password_hash.hexdigest().encode() if self.protocol == 's2k_fo' else password_hash.digest()
                key_length = 32
                return hashlib.pbkdf2_hmac('sha256', password_digest, self.salt, self.iterations, key_length)

        # Step 1: client generates private key a (stored in srp.User) and public key A, sends to server
        srp_password = SrpPassword(self.user["password"])
        srp.rfc5054_enable()
        srp.no_username_in_x()
        usr = srp.User(self.user["accountName"], srp_password, hash_alg=srp.SHA256, ng_type=srp.NG_2048)
        uname, A = usr.start_authentication()
        data = {
            'a': base64.b64encode(A).decode(),
            'accountName': uname,
            'protocols': ['s2k', 's2k_fo']
        }

        headers = self._get_auth_headers()
        try:
            response = self.session.post("%s/signin/init" % self.AUTH_ENDPOINT, data=json.dumps(data), headers=headers)
            if response.status_code == 401:
                raise PyiCloudAPIResponseException(response.text, str(response.status_code))
        except PyiCloudAPIResponseException as error:
            msg = "Failed to initiate srp authentication."
            raise PyiCloudFailedLoginException(msg, error) from error

        # Step 2: server sends public key B, salt, and c to client
        body = response.json()
        salt = base64.b64decode(body['salt'])
        b = base64.b64decode(body['b'])
        c = body['c']
        iterations = body['iteration']
        protocol = body['protocol']

        # Step 3: client generates session key M1 and M2 with salt and b, sends to server
        srp_password.set_encrypt_info(protocol, salt, iterations)
        m1 = usr.process_challenge( salt, b )
        m2 = usr.H_AMK

        data = {
            "accountName": uname,
            "c": c,
            "m1": base64.b64encode(m1).decode(),
            "m2": base64.b64encode(m2).decode(),
            "rememberMe": True,
            "trustTokens": [],
        }

        if self.session_data.get("trust_token"):
            data["trustTokens"] = [self.session_data.get("trust_token")]

        try:
            response = self.session.post(
                "%s/signin/complete" % self.AUTH_ENDPOINT,
                params={"isRememberMeEnabled": "true"},
                data=json.dumps(data),
                headers=headers,
            )
            if response.status_code == 409:
                # requires 2FA
                pass
            elif response.status_code == 412:
                # non 2FA account returns 412 "precondition no met"
                headers = self._get_auth_headers()
                response = self.session.post(
                    "%s/repair/complete" % self.AUTH_ENDPOINT,
                    data=json.dumps({}),
                    headers=headers,
                )
            elif response.status_code >= 400 and response.status_code < 600:
                raise PyiCloudAPIResponseException(response.text, str(response.status_code))
        except PyiCloudAPIResponseException as error:
            msg = "Invalid email/password combination."
            raise PyiCloudFailedLoginException(msg, error) from error

    def _authenticate_raw_password(self) -> None:
        data = dict(self.user)

        data["rememberMe"] = True
        data["trustTokens"] = []
        if self.session_data.get("trust_token"):
            data["trustTokens"] = [self.session_data.get("trust_token")]

        headers = self._get_auth_headers()
        try:
            self.session.post(
                "%s/signin" % self.AUTH_ENDPOINT,
                params={"isRememberMeEnabled": "true"},
                data=json.dumps(data),
                headers=headers,
            )
        except PyiCloudAPIResponseException as error:
            msg = "Invalid email/password combination."
            raise PyiCloudFailedLoginException(msg, error) from error

    def _validate_token(self) -> Dict[str, Any]:
        """Checks if the current access token is still valid."""
        LOGGER.debug("Checking session token validity")
        try:
            req = self.session.post("%s/validate" % self.SETUP_ENDPOINT, data="null")
            LOGGER.debug("Session token is still valid")
            result: Dict[str, Any] = req.json()
            return result
        except PyiCloudAPIResponseException as err:
            LOGGER.debug("Invalid authentication token")
            raise err

    def _get_auth_headers(self, overrides: Optional[Dict[str, str]]=None) -> Dict[str, str]:
        headers = {
            "Accept": "application/json, text/javascript",
            "Content-Type": "application/json",
            "X-Apple-OAuth-Client-Id": "d39ba9916b7251055b22c7f910e2ea796ee65e98b2ddecea8f5dde8d9d1a815d",
            "X-Apple-OAuth-Client-Type": "firstPartyAuth",
            "X-Apple-OAuth-Redirect-URI": "https://www.icloud.com",
            "X-Apple-OAuth-Require-Grant-Code": "true",
            "X-Apple-OAuth-Response-Mode": "web_message",
            "X-Apple-OAuth-Response-Type": "code",
            "X-Apple-OAuth-State": self.client_id,
            "X-Apple-Widget-Key": "d39ba9916b7251055b22c7f910e2ea796ee65e98b2ddecea8f5dde8d9d1a815d",
        }
        scnt = self.session_data.get("scnt")
        if scnt:
            headers["scnt"] = scnt

        session_id = self.session_data.get("session_id")
        if session_id:
            headers["X-Apple-ID-Session-Id"] = session_id

        if overrides:
            headers.update(overrides)
        return headers

    @property
    def cookiejar_path(self) -> str:
        """Get path for cookiejar file."""
        return path.join(
            self._cookie_directory,
            "".join([c for c in self.user.get("accountName") if match(r"\w", c)]), # type: ignore[union-attr]
        )

    @property
    def session_path(self) -> str:
        """Get path for session data file."""
        return path.join(
            self._cookie_directory,
            "".join([c for c in self.user.get("accountName") if match(r"\w", c)]) # type: ignore[union-attr]
            + ".session",
        )

    @property
    def requires_2sa(self) -> bool:
        """Returns True if two-step authentication is required."""
        return self.data.get("dsInfo", {}).get("hsaVersion", 0) >= 1 and (
            self.data.get("hsaChallengeRequired", False) or not self.is_trusted_session
        )

    @property
    def requires_2fa(self) -> bool:
        """Returns True if two-factor authentication is required."""
        return self.data["dsInfo"].get("hsaVersion", 0) == 2 and (
            self.data.get("hsaChallengeRequired", False) or not self.is_trusted_session
        ) and self.data["dsInfo"].get("hasICloudQualifyingDevice", False)

    @property
    def is_trusted_session(self) -> bool:
        """Returns True if the session is trusted."""
        return typing.cast(bool, self.data.get("hsaTrustedBrowser", False))

    @property
    def trusted_devices(self) -> Sequence[Dict[str, Any]]:
        """ Returns devices trusted for two-step authentication."""
        request = self.session.get(
            '%s/listDevices' % self.SETUP_ENDPOINT,
            params=self.params
        )
        devices: Optional[Sequence[Dict[str, Any]]] = request.json().get('devices')
        if devices:
            return devices
        return []

    def send_request(self, request: PreparedRequest) -> Response:
        return self.session.send(request)

    def get_oauth_session(self) -> AuthenticatedSession:
        return AuthenticatedSession(client_id = self.client_id, scnt = self.session_data["scnt"], session_id = self.session_data["session_id"])

    def get_trusted_phone_numbers(self) -> Sequence[TrustedDevice]:
        """ Returns list of trusted phone number for sms 2fa """

        oauth_session = self.get_oauth_session()
        context = TrustedPhoneContextProvider(domain = self.domain, oauth_session=oauth_session)

        req = build_trusted_phone_numbers_request(context)
        request = Request(
            method = req.method,
            url = req.url,
            headers= req.headers
        ).prepare()

        response = self.send_request(request)
        
        return parse_trusted_phone_numbers_response(response)

    def send_2fa_code_sms(self, device_id: int) -> bool:
        """ Requests that a verification code is sent to the given device"""

        oauth_session = self.get_oauth_session()
        context = TrustedPhoneContextProvider(domain = self.domain, oauth_session=oauth_session)

        req = build_send_sms_code_request(context, device_id)
        request = Request(
            method = req.method,
            url = req.url,
            headers= req.headers,
            data = req.data,
            json = req.json,
        ).prepare()

        response = self.send_request(request)
        
        return response.ok

    def send_verification_code(self, device: Dict[str, Any]) -> bool:
        """ Requests that a verification code is sent to the given device"""
        data = json.dumps(device)
        request = self.session.post(
            '%s/sendVerificationCode' % self.SETUP_ENDPOINT,
            params=self.params,
            data=data
        )
        return typing.cast(bool, request.json().get('success', False))

    def validate_verification_code(self, device: Dict[str, Any], code: str) -> bool:
        """Verifies a verification code received on a trusted device."""
        device.update({"verificationCode": code, "trustBrowser": True})
        data = json.dumps(device)

        try:
            self.session.post(
                "%s/validateVerificationCode" % self.SETUP_ENDPOINT,
                params=self.params,
                data=data,
            )
        except PyiCloudAPIResponseException as error:
            if str(error.code) == "-21669":
                # Wrong verification code
                return False
            raise

        # When validating a code through the 2SA endpoint
        # the /2sv/trust URL returns 404 and won't return a trust token
        # self.trust_session()
        self._authenticate_with_token()

        return not self.requires_2sa

    def validate_2fa_code_sms(self, device_id: int, code:str) -> bool:
        """Verifies a verification code received via Apple's 2FA system through SMS."""

        oauth_session = self.get_oauth_session()
        context = TrustedPhoneContextProvider(domain = self.domain, oauth_session=oauth_session)

        req = build_verify_sms_code_request(context, device_id, code)
        request = Request(
            method = req.method,
            url = req.url,
            headers= req.headers,
            data = req.data,
            json = req.json,
        ).prepare()
        response = self.send_request(request)
        
        if response.ok:
            return self.trust_session()
        return False


    def validate_2fa_code(self, code:str) -> bool:
        """Verifies a verification code received via Apple's 2FA system (HSA2)."""
        data = {"securityCode": {"code": code}}

        headers = self._get_auth_headers({"Accept": "application/json"})

        try:
            self.session.post(
                "%s/verify/trusteddevice/securitycode" % self.AUTH_ENDPOINT,
                data=json.dumps(data),
                headers=headers,
            )
        except PyiCloudAPIResponseException as error:
            if str(error.code) == "-21669":
                # Wrong verification code
                LOGGER.error("Code verification failed.")
                return False
            raise

        LOGGER.debug("Code verification successful.")

        self.trust_session()
        return not self.requires_2sa

    def trust_session(self) -> bool:
        """Request session trust to avoid user log in going forward."""
        headers = self._get_auth_headers()

        try:
            self.session.get(
                f"{self.AUTH_ENDPOINT}/2sv/trust",
                headers=headers,
            )
            self._authenticate_with_token()
            return True
        except PyiCloudAPIResponseException:
            LOGGER.error("Session trust failed.")
            return False

    def _get_webservice_url(self, ws_key: str) -> str:
        """Get webservice URL, raise an exception if not exists."""
        if self._webservices.get(ws_key) is None:
            raise PyiCloudServiceNotActivatedException(
                "Webservice not available", ws_key
            )
        return typing.cast(str, self._webservices[ws_key]["url"])

    @property
    def devices(self) -> Sequence[AppleDevice]: 
        """ Return all devices."""
        service_root = self._get_webservice_url("findme")
        return typing.cast(Sequence[AppleDevice], FindMyiPhoneServiceManager(
            service_root,
            self.session,
            self.params
        ))

    @property
    def account(self): # type: ignore
        service_root = self._gget_webservice_url("account") # type: ignore
        return AccountService( # type: ignore
            service_root,
            self.session,
            self.params
        )

    @property
    def iphone(self): # type: ignore
        return self.devices[0]

    @property
    def files(self): # type: ignore
        if not hasattr(self, '_files'):
            service_root = self._get_webservice_url("ubiquity")
            self._files = UbiquityService( # type: ignore
                service_root,
                self.session,
                self.params
            )
        return self._files

    @property
    def photos(self) -> PhotosService:
        """Gets the 'Photo' service."""
        if not self._photos:
            service_root = self._get_webservice_url("ckdatabasews")
            self._photos = PhotosService(
                service_root, 
                self.session, 
                self.params, 
                self.filename_cleaner, 
                self.lp_filename_generator, 
                self.raw_policy,
                self.file_match_policy
                )
        return self._photos

    @property
    def calendar(self): # type: ignore
        service_root = self._get_webservice_url("calendar")
        return CalendarService(service_root, self.session, self.params)# type: ignore

    @property
    def contacts(self): # type: ignore
        service_root = self._get_webservice_url("contacts")
        return ContactsService(service_root, self.session, self.params)# type: ignore

    @property
    def reminders(self): # type: ignore
        service_root = self._get_webservice_url("reminders")
        return RemindersService(service_root, self.session, self.params)# type: ignore

    def __unicode__(self) -> str:
        return 'iCloud API: %s' % self.user.get('accountName')

    def __str__(self) -> str:
        as_unicode = self.__unicode__()
        if sys.version_info[0] >= 3:
            return as_unicode
        else:
            return as_unicode.encode('ascii', 'ignore')

    def __repr__(self) -> str:
        return '<%s>' % str(self)
