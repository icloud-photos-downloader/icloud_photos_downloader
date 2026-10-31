import base64
import json
from contextlib import nullcontext
from types import SimpleNamespace
from typing import Any
from unittest import TestCase, mock

from fido2.client import ClientError

from icloudpd.authentication import request_2fa, request_security_key
from icloudpd.logger import setup_logger
from pyicloud_ipd.base import PyiCloudService
from pyicloud_ipd.exceptions import PyiCloudAPIResponseException, PyiCloudFailedMFAException

CHALLENGE = {
    "challenge": "Y2hhbGxlbmdl",  # base64url("challenge")
    "keyHandles": ["a2V5MQ", "a2V5Mg"],  # base64url("key1"), base64url("key2")
    "rpId": "apple.com",
}


def make_service(auth_response: Any = None) -> SimpleNamespace:
    """Stand-in for PyiCloudService: only what the security key methods touch."""
    session = mock.Mock()
    session.get.return_value.json.return_value = auth_response
    return SimpleNamespace(
        AUTH_ENDPOINT="https://idmsa.apple.com/appleauth/auth",
        response_observer=mock.Mock(),
        cookie_obfuscate_rules=[],
        header_obfuscate_rules=[],
        header_pass_rules=[],
        header_drop_rules=[],
        use_rules=lambda rules: nullcontext(rules),
        _get_auth_headers=lambda overrides=None: dict(overrides or {}),
        trust_session=mock.Mock(return_value=True),
        session=session,
    )


def b64(value: bytes) -> str:
    return base64.b64encode(value).decode()


class GetSecurityKeyChallengeTestCase(TestCase):
    def test_security_key_account(self) -> None:
        service = make_service({"fsaChallenge": CHALLENGE, "keyNames": ["Key 1"]})
        service.response_observer = None

        result = PyiCloudService.get_security_key_challenge(service)  # type: ignore[arg-type]

        self.assertEqual({**CHALLENGE, "keyNames": ["Key 1"]}, result)

    def test_no_challenge(self) -> None:
        for response in [
            {"trustedPhoneNumbers": [{"id": 1}]},
            {"fsaChallenge": {"challenge": "abc"}},
            ["not", "an", "object"],
            ValueError("not json"),
            PyiCloudAPIResponseException("Invalid session.", "-20528"),
        ]:
            with self.subTest(response=response):
                service = make_service(response)
                if isinstance(response, ValueError):
                    service.session.get.return_value.json.side_effect = response
                if isinstance(response, PyiCloudAPIResponseException):
                    service.session.get.side_effect = response

                self.assertIsNone(PyiCloudService.get_security_key_challenge(service))  # type: ignore[arg-type]


@mock.patch("fido2.client.Fido2Client")
@mock.patch("fido2.hid.CtapHidDevice.list_devices", return_value=["key"])
class ConfirmSecurityKeyTestCase(TestCase):
    def setUp(self) -> None:
        self.service = make_service()

    def sign(self, client: mock.Mock) -> None:
        client.get_assertion.return_value.get_response.return_value = mock.Mock(
            response=mock.Mock(
                client_data=b"client_data",
                signature=b"signature",
                authenticator_data=b"authenticator_data",
                user_handle=b"user",
            ),
            raw_id=b"credential_id",
        )

    def confirm(self) -> bool:
        return PyiCloudService.confirm_security_key(self.service, CHALLENGE)  # type: ignore[arg-type]

    def test_signs_posts_and_trusts(self, _: mock.Mock, client: mock.Mock) -> None:
        self.sign(client.return_value)

        self.assertTrue(self.confirm())

        options = client.return_value.get_assertion.call_args.args[0]
        self.assertEqual(b"challenge", options.challenge)
        self.assertEqual([b"key1", b"key2"], [c.id for c in options.allow_credentials])
        post = self.service.session.post.call_args
        self.assertEqual("https://idmsa.apple.com/appleauth/auth/verify/security/key", post.args[0])
        self.assertEqual(
            {
                "challenge": "Y2hhbGxlbmdl",
                "clientData": b64(b"client_data"),
                "signatureData": b64(b"signature"),
                "authenticatorData": b64(b"authenticator_data"),
                "userHandle": b64(b"user"),
                "credentialID": b64(b"credential_id"),
                "rpId": "apple.com",
            },
            json.loads(post.kwargs["data"]),
        )
        self.service.trust_session.assert_called_once()

    def test_any_registered_key(self, list_devices: mock.Mock, client: mock.Mock) -> None:
        list_devices.return_value = ["unregistered", "registered"]
        clients = {"unregistered": mock.Mock(), "registered": mock.Mock()}
        clients["unregistered"].get_assertion.side_effect = ClientError(
            ClientError.ERR.DEVICE_INELIGIBLE  # type: ignore[no-untyped-call]
        )
        self.sign(clients["registered"])
        client.side_effect = lambda device, **_: clients[device]

        self.assertTrue(self.confirm())

        cancel = clients["registered"].get_assertion.call_args.kwargs["event"]
        self.assertTrue(cancel.is_set())
        self.service.trust_session.assert_called_once()

    def test_no_key_plugged_in(self, list_devices: mock.Mock, _: mock.Mock) -> None:
        list_devices.return_value = []

        self.assertFalse(self.confirm())
        self.service.session.post.assert_not_called()

    def test_key_not_touched(self, _: mock.Mock, client: mock.Mock) -> None:
        client.return_value.get_assertion.side_effect = ClientError(ClientError.ERR.TIMEOUT)  # type: ignore[no-untyped-call]

        self.assertFalse(self.confirm())
        self.service.session.post.assert_not_called()

    def test_apple_rejects_assertion(self, _: mock.Mock, client: mock.Mock) -> None:
        self.sign(client.return_value)
        self.service.response_observer = None
        self.service.session.post.side_effect = PyiCloudAPIResponseException("Rejected", "-20101")

        self.assertFalse(self.confirm())
        self.service.trust_session.assert_not_called()


class RequestSecurityKeyTestCase(TestCase):
    def test_security_key_instead_of_code(self) -> None:
        challenge = {**CHALLENGE, "keyNames": ["Key 1", "Key 2"]}
        icloud = mock.Mock()
        icloud.get_trusted_phone_numbers.return_value = []
        icloud.get_security_key_challenge.return_value = challenge

        with mock.patch("icloudpd.authentication.echo") as echo:
            request_2fa(icloud, setup_logger())

        echo.assert_called_once_with("Plug in a security key (Key 1, Key 2) and touch it")
        icloud.confirm_security_key.assert_called_once_with(challenge)
        icloud.trigger_push_notification.assert_not_called()

    def test_no_phone_numbers_and_no_security_key(self) -> None:
        icloud = mock.Mock()
        icloud.get_trusted_phone_numbers.return_value = []
        icloud.get_security_key_challenge.return_value = None

        with mock.patch("icloudpd.authentication.prompt_string", return_value="123456"):
            request_2fa(icloud, setup_logger())

        icloud.validate_2fa_code.assert_called_once_with("123456")
        icloud.confirm_security_key.assert_not_called()

    def test_failure_raises(self) -> None:
        icloud = mock.Mock(confirm_security_key=mock.Mock(return_value=False))

        with (
            mock.patch("icloudpd.authentication.echo") as echo,
            self.assertRaises(PyiCloudFailedMFAException),
        ):
            request_security_key(icloud, setup_logger(), {**CHALLENGE, "keyNames": []})

        echo.assert_called_once_with("Plug in a security key and touch it")
