import inspect
import json
import logging
import typing
from typing import Any, Callable, Dict, Mapping, NoReturn, Sequence

from requests import Response, Session
from typing_extensions import override

from foundation.http import response_to_har_entry
from pyicloud_ipd.exceptions import (
    PyiCloud2SARequiredException,
    PyiCloudAPIResponseException,
    PyiCloudServiceNotActivatedException,
)
from pyicloud_ipd.utils import handle_connection_error, throw_on_503

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


class PyiCloudPasswordFilter(logging.Filter):
    def __init__(self, password: str):
        super().__init__(password)

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if self.name in message:
            record.msg = message.replace(self.name, "********")
            record.args = []  # type: ignore[assignment]

        return True


class PyiCloudSession(Session):
    """iCloud session."""

    def __init__(
        self, service: Any, response_observer: Callable[[Mapping[str, Any]], None] | None = None
    ):
        self.service = service
        self.response_observer = response_observer
        super().__init__()

    def observe(self, response: Response) -> Response:
        if self.response_observer:
            self.response_observer(response_to_har_entry(response))
        return response

    @override
    def request(self, method: str, url, **kwargs):  # type: ignore
        # Charge logging to the right service endpoint
        callee = inspect.stack()[2]
        module = inspect.getmodule(callee[0])
        request_logger = logging.getLogger(module.__name__).getChild("http")  # type: ignore[union-attr]
        if (
            self.service.password_filter
            and self.service.password_filter not in request_logger.filters
        ):
            request_logger.addFilter(self.service.password_filter)

        request_logger.debug("%s %s %s", method, url, kwargs.get("data", ""))

        if "timeout" not in kwargs and self.service.http_timeout is not None:
            kwargs["timeout"] = self.service.http_timeout
        response = throw_on_503(
            self.observe(handle_connection_error(super().request)(method, url, **kwargs))
        )

        content_type = response.headers.get("Content-Type", "").split(";")[0]
        json_mimetypes = ["application/json", "text/json"]

        request_logger.debug(response.headers)

        for header, value in HEADER_DATA.items():
            if response.headers.get(header):
                session_arg = value
                self.service.session_data.update({session_arg: response.headers.get(header)})

        # Save session_data to file
        with open(self.service.session_path, "w", encoding="utf-8") as outfile:
            json.dump(self.service.session_data, outfile)
            LOGGER.debug("Saved session data to file")

        # Save cookies to file
        self.cookies.save(ignore_discard=True, ignore_expires=True)  # type: ignore[attr-defined]
        LOGGER.debug("Cookies saved to %s", self.service.cookiejar_path)

        if not response.ok and (
            content_type not in json_mimetypes or response.status_code in [421, 450, 500]
        ):
            self._raise_error(str(response.status_code), response.reason)

        if content_type not in json_mimetypes:
            if self.service.session_data.get("apple_rscd") == "401":
                code: str | None = "401"
                reason: str | None = "Invalid username/password combination."
                self._raise_error(code or "Unknown", reason or "Unknown")

            return response

        try:
            data = response.json() if response.status_code != 204 else {}
        except ValueError:
            request_logger.warning("Failed to parse response with JSON mimetype")
            return response

        request_logger.debug(data)

        if isinstance(data, dict):
            if data.get("hasError"):
                errors: Sequence[Dict[str, Any]] | None = typing.cast(
                    Sequence[Dict[str, Any]] | None, data.get("service_errors")
                )
                # service_errors returns a list of dict
                #    dict includes the keys: code, title, message, supressDismissal
                # Assuming a single error for now
                # May need to revisit to capture and handle multiple errors
                if errors:
                    code = errors[0].get("code")
                    reason = errors[0].get("message")
                self._raise_error(code or "Unknown", reason or "Unknown")
            elif not data.get("success"):
                reason = data.get("errorMessage")
                reason = reason or data.get("reason")
                reason = reason or data.get("errorReason")
                if not reason and isinstance(data.get("error"), str):
                    reason = data.get("error")
                if not reason and data.get("error"):
                    reason = "Unknown reason"

                code = data.get("errorCode")
                if not code and data.get("serverErrorCode"):
                    code = data.get("serverErrorCode")
                if not code and data.get("error"):
                    code = data.get("error")

                if reason:
                    self._raise_error(code or "Unknown", reason)

        return response

    def _raise_error(self, code: str, reason: str) -> NoReturn:
        if self.service.requires_2sa and reason == "Missing X-APPLE-WEBAUTH-TOKEN cookie":
            raise PyiCloud2SARequiredException(self.service.user["accountName"])
        if code in ("ZONE_NOT_FOUND", "AUTHENTICATION_FAILED"):
            reason = (
                "Apple iCloud setup is not complete. Please log into https://icloud.com/ to manually "
                "finish setting up your iCloud service"
            )
            api_error: Exception = PyiCloudServiceNotActivatedException(reason, code)
            LOGGER.error(api_error)

            raise (api_error)
        if code == "ACCESS_DENIED":
            reason = (
                reason + ".  Please wait a few minutes then try again."
                "The remote servers might be trying to throttle requests."
            )
        if code in ["421", "450", "500"]:
            reason = "Authentication required for Account."

        api_error = PyiCloudAPIResponseException(reason, code)
        LOGGER.error(api_error)
        raise api_error
