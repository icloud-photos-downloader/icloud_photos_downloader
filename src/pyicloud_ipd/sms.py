from html.parser import HTMLParser
import json
from typing import Any, List, Mapping, NamedTuple, Optional, Protocol, Sequence, Tuple

class _SMSParser(HTMLParser):
    def __init__(self) -> None:
        # initialize the base class
        super(_SMSParser, self).__init__()
        self._is_boot_args = False
        self.sms_data: Mapping[str, Any] = {}

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if tag == "script":
            self._is_boot_args = ("type", "application/json") in attrs and ("class", "boot_args") in attrs

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self._is_boot_args = False

    def handle_data(self, data: str) -> None:
        if self._is_boot_args:
            self.sms_data = json.loads(data)

class TrustedDevice(Protocol):
    @property
    def id(self) -> int: ...
    @property
    def obfuscated_number(self) -> str: ...

class _InternalTrustedDevice(NamedTuple):
    id: int
    obfuscated_number: str

def _map_to_trusted_device(device: Mapping[str, Any]) -> TrustedDevice:
    return _InternalTrustedDevice(id=device["id"], obfuscated_number=device["obfuscatedNumber"])

def parse_trusted_phone_numbers_response(content: str) -> Sequence[TrustedDevice]:
    """ Parses html response for the list of available trusted phone numbers"""
    parser = _SMSParser()
    parser.feed(content)
    parser.close()
    numbers: Sequence[Mapping[str, Any]] = parser.sms_data.get("direct", {}).get("twoSV", {}).get("phoneNumberVerification", {}).get("trustedPhoneNumbers", [])
    return list(map(_map_to_trusted_device, numbers))

class AuthenticatedSession(NamedTuple):
    client_id: str
    scnt: str
    session_id: str

def _oauth_const_headers() -> Mapping[str, str]:
    return {
        "X-Apple-OAuth-Client-Id": "d39ba9916b7251055b22c7f910e2ea796ee65e98b2ddecea8f5dde8d9d1a815d",
        "X-Apple-OAuth-Client-Type": "firstPartyAuth",
        "X-Apple-OAuth-Require-Grant-Code": "true",
        "X-Apple-Widget-Key": "d39ba9916b7251055b22c7f910e2ea796ee65e98b2ddecea8f5dde8d9d1a815d",
    }

def _oauth_redirect_header(domain: str) -> Mapping[str, str]:
    return {
        "X-Apple-OAuth-Redirect-URI": "https://www.icloud.com.cn" if domain == "cn" else "https://www.icloud.com",
    }

def _oauth_headers(auth_session: AuthenticatedSession) -> Mapping[str, str]:
    """ Headers with OAuth session """

    return {
        "X-Apple-OAuth-State": auth_session.client_id,
        "scnt": auth_session.scnt,
        "X-Apple-ID-Session-Id": auth_session.session_id
    }

def _auth_url(domain: str) -> str:
    return "https://idmsa.apple.com.cn/appleauth/auth" if domain == "cn" else "https://idmsa.apple.com/appleauth/auth"

class _DomainProvider(Protocol):
    @property
    def domain(self) -> str: ...

class _OAuthSessionProvider(Protocol):
    @property
    def oauth_session(self) -> AuthenticatedSession: ...

class _TrustedPhoneContextProvider(_DomainProvider, _OAuthSessionProvider, Protocol): ...

class Request(Protocol):
    @property
    def method(self) -> str: ...
    @property
    def url(self) -> str: ...
    @property
    def headers(self) -> Mapping[str, str]: ...

class _InternalRequest(NamedTuple):
    method: str
    url: str
    headers: Mapping[str, str]

def build_trusted_phone_numbers_request(context: _TrustedPhoneContextProvider) -> Request:
    """ Builds a request for the list of trusted phone numbers for sms 2fa """

    url = _auth_url(context.domain)

    req = _InternalRequest(
    method="GET",
    url=url,
    headers = {
        **_oauth_const_headers(),
        **_oauth_redirect_header(context.domain),
        **_oauth_headers(context.oauth_session),
    })
    return req

