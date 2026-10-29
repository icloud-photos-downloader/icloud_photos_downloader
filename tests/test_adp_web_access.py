from types import SimpleNamespace
from typing import Any, Dict, List
from unittest import TestCase, mock

import pytest

from foundation.core import constant
from icloudpd.authentication import authenticator
from icloudpd.base import dummy_password_writter
from icloudpd.logger import setup_logger
from icloudpd.mfa_provider import MFAProvider
from icloudpd.status import StatusExchange
from pyicloud_ipd.base import PyiCloudService
from pyicloud_ipd.exceptions import PyiCloudFailedLoginException

CONSENTED = {"isWebAccessAllowed": True, "isDeviceConsentedForPCS": True}
NOT_CONSENTED = {"isWebAccessAllowed": True, "isDeviceConsentedForPCS": False}


def make_service(responses: List[Dict[str, Any]]) -> SimpleNamespace:
    """Stand-in for PyiCloudService: only what request_pcs_consent touches."""
    session = mock.Mock()
    session.request.side_effect = [
        mock.Mock(json=mock.Mock(return_value=response)) for response in responses
    ]
    return SimpleNamespace(
        params={"dsid": "1"},
        client_id="client",
        SETUP_ENDPOINT="https://setup.icloud.com/setup/ws/1",
        session=session,
    )


def called_endpoints(service: SimpleNamespace) -> List[str]:
    return [call.args[1].rsplit("/", 1)[1] for call in service.session.request.call_args_list]


class RequestPcsConsentTestCase(TestCase):
    @pytest.fixture(autouse=True)
    def no_sleep(self) -> Any:
        with mock.patch("pyicloud_ipd.base.time.sleep") as sleep:
            self.sleep = sleep
            yield

    def test_already_consented(self) -> None:
        service = make_service([CONSENTED, {}, {"status": "success"}])

        PyiCloudService.request_pcs_consent(service)  # type: ignore[arg-type]

        self.assertEqual(
            ["requestWebAccessState", "generateSessionIdToken", "requestPCS"],
            called_endpoints(service),
        )
        self.sleep.assert_not_called()

    def test_web_access_disabled(self) -> None:
        service = make_service([{"isWebAccessAllowed": False}])

        with self.assertRaises(PyiCloudFailedLoginException) as context:
            PyiCloudService.request_pcs_consent(service)  # type: ignore[arg-type]

        self.assertIn("Access iCloud Data on the Web", str(context.exception))

    def test_waits_for_device_approval(self) -> None:
        service = make_service(
            [NOT_CONSENTED, {}, NOT_CONSENTED, CONSENTED, {}, {"status": "success"}]
        )

        PyiCloudService.request_pcs_consent(service)  # type: ignore[arg-type]

        self.assertEqual(
            [
                "requestWebAccessState",
                "enableDeviceConsentForPCS",
                "requestWebAccessState",
                "requestWebAccessState",
                "generateSessionIdToken",
                "requestPCS",
            ],
            called_endpoints(service),
        )
        self.assertEqual(2, self.sleep.call_count)

    def test_approval_timeout(self) -> None:
        service = make_service([NOT_CONSENTED, {}])

        with (
            mock.patch("pyicloud_ipd.base.time.monotonic", side_effect=[0, 1000]),
            self.assertRaises(PyiCloudFailedLoginException) as context,
        ):
            PyiCloudService.request_pcs_consent(service)  # type: ignore[arg-type]

        self.assertIn("Timed out", str(context.exception))

    def test_retries_request_pcs_until_success(self) -> None:
        service = make_service(
            [CONSENTED, {}, {"status": "pending"}, {"status": "pending"}, {"status": "success"}]
        )

        PyiCloudService.request_pcs_consent(service)  # type: ignore[arg-type]

        self.assertEqual(["requestPCS"] * 3, called_endpoints(service)[2:])
        self.assertEqual(2, self.sleep.call_count)

    def test_warns_when_request_pcs_never_succeeds(self) -> None:
        service = make_service([CONSENTED, {}] + [{"status": "pending"}] * 11)

        with self.assertLogs("pyicloud_ipd.base", level="WARNING") as logs:
            PyiCloudService.request_pcs_consent(service)  # type: ignore[arg-type]

        self.assertEqual(["requestPCS"] * 11, called_endpoints(service)[2:])
        self.assertIn("did not confirm web access to photos data", logs.output[0])


class AuthenticatorAdpTestCase(TestCase):
    def authenticate(self, adp_web_access: bool) -> mock.Mock:
        with mock.patch("icloudpd.authentication.PyiCloudService") as service_class:
            service = service_class.return_value
            service.requires_2fa = False
            service.requires_2sa = False
            authenticator(
                setup_logger(),
                "com",
                {"test": (constant("dummy"), dummy_password_writter)},
                MFAProvider.CONSOLE,
                StatusExchange(),
                "user",
                lambda: None,
                adp_web_access=adp_web_access,
            )
        return service  # type: ignore[no-any-return]

    def test_requests_consent_when_enabled(self) -> None:
        self.authenticate(True).request_pcs_consent.assert_called_once_with("photos")

    def test_skips_consent_by_default(self) -> None:
        self.authenticate(False).request_pcs_consent.assert_not_called()
