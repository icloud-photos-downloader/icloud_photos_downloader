import base64
import getpass
import hashlib
import http.cookiejar as cookielib
import json
import logging
import typing
from contextlib import contextmanager
from functools import partial
from itertools import chain
from os import mkdir, path
from re import Pattern, match
from tempfile import gettempdir
from typing import Any, Callable, Dict, Generator, List, Mapping, NamedTuple, Sequence
from uuid import uuid1

import srp
from requests import PreparedRequest, Request, Response

from foundation.core import compose, constant, identity
from foundation.json import (
    Rule,
    apply_rules,
    re_compile_ignorecase,
)
from foundation.string import obfuscate
from pyicloud_ipd.exceptions import (
    PyiCloudAPIResponseException,
    PyiCloudConnectionException,
    PyiCloudFailedLoginException,
    PyiCloudServiceNotActivatedException,
)
from pyicloud_ipd.services.photos import PhotosService
from pyicloud_ipd.session import PyiCloudPasswordFilter, PyiCloudSession
from pyicloud_ipd.sms import (
    AuthenticatedSession,
    TrustedDevice,
    build_send_sms_code_request,
    build_trusted_phone_numbers_request,
    build_verify_sms_code_request,
    parse_trusted_phone_numbers_response,
)

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


def origin_referer_headers(input: str) -> Dict[str, str]:
    return {"Origin": input, "Referer": f"{input}/"}


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
        domain: str,
        apple_id: str,
        password_provider: Callable[[], str | None],
        response_observer: Callable[[Mapping[str, Any]], None] | None = None,
        cookie_directory: str | None = None,
        verify: bool = True,
        client_id: str | None = None,
        with_family: bool = True,
        http_timeout: float = 30.0,
    ):
        self.apple_id = apple_id
        self.password_provider: Callable[[], str | None] = password_provider
        self.data: Dict[str, Any] = {}
        self.params: Dict[str, Any] = {}
        self.client_id: str = client_id or (f"auth-{str(uuid1()).lower()}")
        self.with_family = with_family
        self.http_timeout = http_timeout
        self.response_observer = response_observer
        self.observer_rules: Sequence[Rule] = []

        # set it when we get password
        self.password_filter: PyiCloudPasswordFilter | None = None

        if domain == "com":
            self.AUTH_ROOT_ENDPOINT = "https://idmsa.apple.com"
            self.AUTH_ENDPOINT = "https://idmsa.apple.com/appleauth/auth"
            self.HOME_ENDPOINT = "https://www.icloud.com"
            self.SETUP_ENDPOINT = "https://setup.icloud.com/setup/ws/1"
        elif domain == "cn":
            self.AUTH_ROOT_ENDPOINT = "https://idmsa.apple.com.cn"
            self.AUTH_ENDPOINT = "https://idmsa.apple.com.cn/appleauth/auth"
            self.HOME_ENDPOINT = "https://www.icloud.com.cn"
            self.SETUP_ENDPOINT = "https://setup.icloud.com.cn/setup/ws/1"
        else:
            raise NotImplementedError(f"Domain '{domain}' is not supported yet")

        self.domain = domain

        if cookie_directory:
            self._cookie_directory = path.expanduser(path.normpath(cookie_directory))
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
        except (FileNotFoundError, json.JSONDecodeError):
            LOGGER.info("Session file does not exist")
        session_client_id: str | None = self.session_data.get("client_id")
        if session_client_id:
            self.client_id = session_client_id
        else:
            self.session_data.update({"client_id": self.client_id})

        def apply_rules_and_observe(response: Mapping[str, Any]) -> None:
            if self.response_observer:
                self.response_observer(apply_rules("", self.observer_rules, response))

        self.session: PyiCloudSession = PyiCloudSession(
            self, apply_rules_and_observe if self.response_observer else None
        )
        self.session.verify = verify
        self.session.headers.update(
            {
                "Origin": self.HOME_ENDPOINT,
                "Referer": f"{self.HOME_ENDPOINT}/",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
            }
        )

        cookiejar_path = self.cookiejar_path
        self.session.cookies = cookielib.LWPCookieJar(filename=cookiejar_path)  # type: ignore[assignment]
        if path.exists(cookiejar_path):
            try:
                self.session.cookies.load(ignore_discard=True, ignore_expires=True)  # type: ignore[attr-defined]
                LOGGER.debug("Read cookies from %s", cookiejar_path)
            except (FileNotFoundError, OSError):
                # Most likely a pickled cookiejar from earlier versions.
                # The cookiejar will get replaced with a valid one after
                # successful authentication.
                LOGGER.warning("Failed to read cookiejar %s", cookiejar_path)

        # Unsure if this is still needed
        self.params = {
            "clientBuildNumber": "2522Project44",
            "clientMasteringNumber": "2522B2",
            "clientId": self.client_id,
        }

        # set observer rules
        def obfuscate_rule(r: Pattern[str]) -> Rule:
            return (r, obfuscate)

        obfuscate_rules_from_pattern: Callable[[Sequence[str]], List[Rule]] = compose(
            list, partial(map, compose(obfuscate_rule, re_compile_ignorecase))
        )
        self.cookie_obfuscate_rules = obfuscate_rules_from_pattern(
            [r"X_APPLE_.*", r"DES.*", r"acn01", r"aasp"]
        )

        self.header_obfuscate_rules = obfuscate_rules_from_pattern([r"X-APPLE-.*", r"scnt"])

        def pass_rule(r: Pattern[str]) -> Rule:
            return (r, identity)

        pass_rules_from_pattern: Callable[[Sequence[str]], List[Rule]] = compose(
            list, partial(map, compose(pass_rule, re_compile_ignorecase))
        )
        self.header_pass_rules = pass_rules_from_pattern(
            [r"^(request|response)\.headers\.(Origin|Referer|Content-Type|Location)$"]
        )

        def drop_rule(r: Pattern[str]) -> Rule:
            return (r, constant(None))

        drop_rules_from_pattern: Callable[[Sequence[str]], List[Rule]] = compose(
            list, partial(map, compose(drop_rule, re_compile_ignorecase))
        )
        self.header_drop_rules: List[Rule] = drop_rules_from_pattern(
            [r"^(request|response)\.headers\..+"]
        )

        self.validate_response_body_obfuscate_rules = obfuscate_rules_from_pattern(
            [
                r"^response\.content\.dsInfo\.appleId$",
                r"^response\.content\.dsInfo\.appleIdAlias$",
                r"^response\.content\.dsInfo\.iCloudAppleIdAlias$",
                r"^response\.content\.dsInfo\.appleIdEntries\.value$",
                r"^response\.content\.dsInfo\.fullName",
                r"^response\.content\.dsInfo\.firstName",
                r"^response\.content\.dsInfo\.lastName",
                r"^response\.content\.dsInfo\.dsid",
                r"^response\.content\.dsInfo\.notificationId",
                r"^response\.content\.dsInfo\.aDsID",
                r"^response\.content\.dsInfo\.primaryEmail",
            ]
        )
        self.validate_response_body_drop_rules = drop_rules_from_pattern(
            [
                r"^response\.content\.webservices\.",
                r"^response\.content\.configBag\.urls\.",
                r"^response\.content\.apps.*",
                r"^response\.content\.dsInfo\.mailFlags",
            ]
        )
        self.auth_srp_init_body_obfuscate_rules = obfuscate_rules_from_pattern(
            [
                r"^request\.content\.accountName",
                r"^request\.content\.a$",
                r"^response\.content\.salt",
                r"^response\.content\.b",
                r"^response\.content\.c",
            ]
        )
        self.auth_srp_init_body_drop_rules = drop_rules_from_pattern([])
        self.auth_srp_complete_body_obfuscate_rules = obfuscate_rules_from_pattern(
            [
                r"^request\.content\.accountName",
                r"^request\.content\.c",
                r"^request\.content\.m1",
                r"^request\.content\.m2",
                r"^request\.content\.trustTokens\.",
            ]
        )
        self.auth_srp_complete_body_drop_rules = drop_rules_from_pattern([])
        self.auth_srp_repair_complete_body_obfuscate_rules = obfuscate_rules_from_pattern([])
        self.auth_srp_repair_complete_body_drop_rules = drop_rules_from_pattern([])
        self.auth_raw_body_obfuscate_rules = obfuscate_rules_from_pattern(
            [
                r"^request\.content\.accountName",
                r"^request\.content\.password",
                r"^request\.content\.trustTokens\.",
            ]
        )
        self.auth_raw_body_drop_rules = drop_rules_from_pattern([])
        self.auth_token_body_obfuscate_rules = list(
            chain(
                obfuscate_rules_from_pattern(
                    [
                        r"^request\.content\.dsWebAuthToken",
                        r"^request\.content\.trustToken",
                    ]
                ),
                self.validate_response_body_obfuscate_rules,
            )
        )
        self.auth_token_body_drop_rules = self.validate_response_body_drop_rules

        self.authenticate()

        self._photos: PhotosService | None = None

    @contextmanager
    def use_rules(self, rules: Sequence[Rule]) -> Generator[Sequence[Rule], Any, None]:
        temp_rules = self.observer_rules
        try:
            self.observer_rules = rules
            yield temp_rules
        finally:
            self.observer_rules = temp_rules

    def authenticate(self, force_refresh: bool = False) -> None:
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

        if not login_successful:
            password = self.password_provider()
            if not password:
                LOGGER.debug("Password Provider did not give any data")
                return None
            # set logging filter
            self.password_filter = PyiCloudPasswordFilter(password)
            LOGGER.addFilter(self.password_filter)

            LOGGER.debug(f"Authenticating as {self.apple_id}")
            self._authenticate_srp(password)
            # try:
            #     self._authenticate_srp(password)
            # except PyiCloudFailedLoginException as error:
            #     LOGGER.error("Failed to login with srp, falling back to old raw password authentication. Error: %s", error)
            #     try:
            #         self._authenticate_raw_password(password)
            #     except PyiCloudFailedLoginException as error:
            #         LOGGER.error("Failed to login with raw password. Error: %s", error)
            #         raise error

            self._authenticate_with_token()

        # Is this needed?
        self.params.update({"dsid": self.data["dsInfo"]["dsid"]})

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
            # set observer with obfuscator
            if self.response_observer:
                rules = list(
                    chain(
                        self.cookie_obfuscate_rules,
                        self.header_obfuscate_rules,
                        self.header_pass_rules,
                        self.header_drop_rules,
                        self.auth_token_body_obfuscate_rules,
                        self.auth_token_body_drop_rules,
                    )
                )
            else:
                rules = []

            with self.use_rules(rules):
                req = self.session.post(
                    f"{self.SETUP_ENDPOINT}/accountLogin", data=json.dumps(data)
                )
            self.data = req.json()
        except PyiCloudAPIResponseException as error:
            msg = "Invalid authentication token."
            raise PyiCloudFailedLoginException(msg, error) from error

        # {'domainToUse': 'iCloud.com'}
        domain_to_use = self.data.get("domainToUse")
        if domain_to_use is not None:
            msg = f"Apple insists on using {domain_to_use} for your request. Please use --domain parameter"
            raise PyiCloudConnectionException(msg)

    def _authenticate_srp(self, password: str) -> None:
        class SrpPassword:
            # srp uses the encoded password at process_challenge(), thus set_encrypt_info() should be called before that
            def __init__(self, password: str):
                self.pwd = password

            def set_encrypt_info(self, protocol: str, salt: bytes, iterations: int) -> None:
                self.protocol = protocol
                self.salt = salt
                self.iterations = iterations

            def encode(self) -> bytes:
                password_hash = hashlib.sha256(self.pwd.encode())
                password_digest = (
                    password_hash.hexdigest().encode()
                    if self.protocol == "s2k_fo"
                    else password_hash.digest()
                )
                key_length = 32
                return hashlib.pbkdf2_hmac(
                    "sha256", password_digest, self.salt, self.iterations, key_length
                )

        # Step 1: client generates private key a (stored in srp.User) and public key A, sends to server
        srp_password = SrpPassword(password)
        srp.rfc5054_enable()
        srp.no_username_in_x()
        usr = srp.User(self.apple_id, srp_password, hash_alg=srp.SHA256, ng_type=srp.NG_2048)
        uname, A = usr.start_authentication()
        data = {
            "a": base64.b64encode(A).decode(),
            "accountName": uname,
            "protocols": ["s2k", "s2k_fo"],
        }

        headers = self._get_auth_headers(origin_referer_headers(self.AUTH_ROOT_ENDPOINT))
        try:
            if self.response_observer:
                rules = list(
                    chain(
                        self.cookie_obfuscate_rules,
                        self.header_obfuscate_rules,
                        self.header_pass_rules,
                        self.header_drop_rules,
                        self.auth_srp_init_body_obfuscate_rules,
                        self.auth_srp_init_body_drop_rules,
                    )
                )
            else:
                rules = []

            with self.use_rules(rules):
                response = self.session.post(
                    f"{self.AUTH_ENDPOINT}/signin/init", data=json.dumps(data), headers=headers
                )
            if response.status_code == 401:
                raise PyiCloudAPIResponseException(response.text, str(response.status_code))
        except PyiCloudAPIResponseException as error:
            msg = "Failed to initiate srp authentication."
            raise PyiCloudFailedLoginException(msg, error) from error

        # Step 2: server sends public key B, salt, and c to client
        body = response.json()
        salt = base64.b64decode(body["salt"])
        b = base64.b64decode(body["b"])
        c = body["c"]
        iterations = body["iteration"]
        protocol = body["protocol"]

        # Step 3: client generates session key M1 and M2 with salt and b, sends to server
        srp_password.set_encrypt_info(protocol, salt, iterations)
        m1 = usr.process_challenge(salt, b)
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
            # set observer with obfuscator
            if self.response_observer:
                rules = list(
                    chain(
                        self.cookie_obfuscate_rules,
                        self.header_obfuscate_rules,
                        self.header_pass_rules,
                        self.header_drop_rules,
                        self.auth_srp_complete_body_obfuscate_rules,
                        self.auth_srp_complete_body_drop_rules,
                    )
                )
            else:
                rules = []

            with self.use_rules(rules):
                response = self.session.post(
                    f"{self.AUTH_ENDPOINT}/signin/complete",
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
                # set observer with obfuscator
                if self.response_observer:
                    rules = list(
                        chain(
                            self.cookie_obfuscate_rules,
                            self.header_obfuscate_rules,
                            self.header_pass_rules,
                            self.header_drop_rules,
                            self.auth_srp_repair_complete_body_obfuscate_rules,
                            self.auth_srp_repair_complete_body_drop_rules,
                        )
                    )
                else:
                    rules = []

                with self.use_rules(rules):
                    response = self.session.post(
                        f"{self.AUTH_ENDPOINT}/repair/complete",
                        data=json.dumps({}),
                        headers=headers,
                    )
            elif response.status_code >= 400 and response.status_code < 600:
                raise PyiCloudAPIResponseException(response.text, str(response.status_code))
        except PyiCloudAPIResponseException as error:
            msg = "Invalid email/password combination."
            raise PyiCloudFailedLoginException(msg, error) from error

    def _authenticate_raw_password(self, password: str) -> None:
        data = {
            "accountName": self.apple_id,
            "password": password,
            "rememberMe": True,
            "trustTokens": [],
        }
        if self.session_data.get("trust_token"):
            data["trustTokens"] = [self.session_data.get("trust_token")]

        headers = self._get_auth_headers(origin_referer_headers(self.AUTH_ROOT_ENDPOINT))
        try:
            # set observer with obfuscator
            if self.response_observer:
                rules = list(
                    chain(
                        self.cookie_obfuscate_rules,
                        self.header_obfuscate_rules,
                        self.header_pass_rules,
                        self.header_drop_rules,
                        self.auth_raw_body_obfuscate_rules,
                        self.auth_raw_body_drop_rules,
                    )
                )
            else:
                rules = []

            with self.use_rules(rules):
                self.session.post(
                    f"{self.AUTH_ENDPOINT}/signin",
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
        headers = origin_referer_headers(self.HOME_ENDPOINT)
        try:
            # set observer with obfuscator
            if self.response_observer:
                rules = list(
                    chain(
                        self.cookie_obfuscate_rules,
                        self.header_obfuscate_rules,
                        self.header_pass_rules,
                        self.header_drop_rules,
                        self.validate_response_body_obfuscate_rules,
                        self.validate_response_body_drop_rules,
                    )
                )
            else:
                rules = []

            with self.use_rules(rules):
                response = self.session.post(
                    f"{self.SETUP_ENDPOINT}/validate", data="null", headers=headers
                )
            LOGGER.debug("Session token is still valid")
            result: Dict[str, Any] = response.json()
            return result
        except PyiCloudAPIResponseException as err:
            LOGGER.debug("Invalid authentication token")
            raise err

    def _get_auth_headers(self, overrides: Dict[str, str] | None = None) -> Dict[str, str]:
        headers = {
            "Accept": "application/json, text/javascript",
            "Content-Type": "application/json",
            "X-Apple-OAuth-Client-Id": "d39ba9916b7251055b22c7f910e2ea796ee65e98b2ddecea8f5dde8d9d1a815d",
            "X-Apple-OAuth-Client-Type": "firstPartyAuth",
            "X-Apple-OAuth-Redirect-URI": "https://www.icloud.com.cn"
            if self.domain == "cn"
            else "https://www.icloud.com",
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
            "".join([c for c in self.apple_id if match(r"\w", c)]),
        )

    @property
    def session_path(self) -> str:
        """Get path for session data file."""
        return path.join(
            self._cookie_directory,
            "".join([c for c in self.apple_id if match(r"\w", c)]) + ".session",
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
        return (
            self.data["dsInfo"].get("hsaVersion", 0) == 2
            and (self.data.get("hsaChallengeRequired", False) or not self.is_trusted_session)
            and self.data["dsInfo"].get("hasICloudQualifyingDevice", False)
        )

    @property
    def is_trusted_session(self) -> bool:
        """Returns True if the session is trusted."""
        return typing.cast(bool, self.data.get("hsaTrustedBrowser", False))

    @property
    def trusted_devices(self) -> Sequence[Dict[str, Any]]:
        """Returns devices trusted for two-step authentication."""
        request = self.session.get(f"{self.SETUP_ENDPOINT}/listDevices", params=self.params)
        devices: Sequence[Dict[str, Any]] | None = request.json().get("devices")
        if devices:
            return devices
        return []

    def send_request(self, request: PreparedRequest) -> Response:
        return self.session.send(request)

    def get_oauth_session(self) -> AuthenticatedSession:
        return AuthenticatedSession(
            client_id=self.client_id,
            scnt=self.session_data["scnt"],
            session_id=self.session_data["session_id"],
        )

    def get_trusted_phone_numbers(self) -> Sequence[TrustedDevice]:
        """Returns list of trusted phone number for sms 2fa"""

        oauth_session = self.get_oauth_session()
        context = TrustedPhoneContextProvider(domain=self.domain, oauth_session=oauth_session)

        req = build_trusted_phone_numbers_request(context)
        request = Request(method=req.method, url=req.url, headers=req.headers).prepare()

        if self.response_observer:
            rules = list(
                chain(
                    self.cookie_obfuscate_rules,
                    self.header_obfuscate_rules,
                    self.header_pass_rules,
                    self.header_drop_rules,
                )
            )
        else:
            rules = []

        with self.use_rules(rules):
            response = self.send_request(request)

        return parse_trusted_phone_numbers_response(response)

    def send_2fa_code_sms(self, device_id: int) -> bool:
        """Requests that a verification code is sent to the given device"""

        oauth_session = self.get_oauth_session()
        context = TrustedPhoneContextProvider(domain=self.domain, oauth_session=oauth_session)

        req = build_send_sms_code_request(context, device_id)
        request = Request(
            method=req.method,
            url=req.url,
            headers=req.headers,
            data=req.data,
            json=req.json,
        ).prepare()

        if self.response_observer:
            rules = list(
                chain(
                    self.cookie_obfuscate_rules,
                    self.header_obfuscate_rules,
                    self.header_pass_rules,
                    self.header_drop_rules,
                )
            )
        else:
            rules = []

        with self.use_rules(rules):
            response = self.send_request(request)

        return response.ok

    def send_verification_code(self, device: Dict[str, Any]) -> bool:
        """Requests that a verification code is sent to the given device"""
        data = json.dumps(device)
        request = self.session.post(
            f"{self.SETUP_ENDPOINT}/sendVerificationCode", params=self.params, data=data
        )
        return typing.cast(bool, request.json().get("success", False))

    def validate_verification_code(self, device: Dict[str, Any], code: str) -> bool:
        """Verifies a verification code received on a trusted device."""
        device.update({"verificationCode": code, "trustBrowser": True})
        data = json.dumps(device)

        try:
            self.session.post(
                f"{self.SETUP_ENDPOINT}/validateVerificationCode",
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

    def validate_2fa_code_sms(self, device_id: int, code: str) -> bool:
        """Verifies a verification code received via Apple's 2FA system through SMS."""

        oauth_session = self.get_oauth_session()
        context = TrustedPhoneContextProvider(domain=self.domain, oauth_session=oauth_session)

        req = build_verify_sms_code_request(context, device_id, code)
        request = Request(
            method=req.method,
            url=req.url,
            headers=req.headers,
            data=req.data,
            json=req.json,
        ).prepare()
        if self.response_observer:
            rules = list(
                chain(
                    self.cookie_obfuscate_rules,
                    self.header_obfuscate_rules,
                    self.header_pass_rules,
                    self.header_drop_rules,
                )
            )
        else:
            rules = []

        with self.use_rules(rules):
            response = self.send_request(request)

        if response.ok:
            return self.trust_session()
        return False

    def validate_2fa_code(self, code: str) -> bool:
        """Verifies a verification code received via Apple's 2FA system (HSA2)."""
        data = {"securityCode": {"code": code}}

        headers = self._get_auth_headers({"Accept": "application/json"})

        try:
            if self.response_observer:
                rules = list(
                    chain(
                        self.cookie_obfuscate_rules,
                        self.header_obfuscate_rules,
                        self.header_pass_rules,
                        self.header_drop_rules,
                    )
                )
            else:
                rules = []

            with self.use_rules(rules):
                self.session.post(
                    f"{self.AUTH_ENDPOINT}/verify/trusteddevice/securitycode",
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
            if self.response_observer:
                rules = list(
                    chain(
                        self.cookie_obfuscate_rules,
                        self.header_obfuscate_rules,
                        self.header_pass_rules,
                        self.header_drop_rules,
                    )
                )
            else:
                rules = []

            with self.use_rules(rules):
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
            raise PyiCloudServiceNotActivatedException("Webservice not available", ws_key)
        return typing.cast(str, self._webservices[ws_key]["url"])

    @property
    def photos(self) -> PhotosService:
        """Gets the 'Photo' service."""
        if not self._photos:
            service_root = self._get_webservice_url("ckdatabasews")
            self._photos = PhotosService(service_root, self.session, self.params)
        return self._photos

    def __unicode__(self) -> str:
        return f"iCloud API: {self.apple_id}"

    def __str__(self) -> str:
        as_unicode = self.__unicode__()
        return as_unicode

    def __repr__(self) -> str:
        return f"<{str(self)}>"
