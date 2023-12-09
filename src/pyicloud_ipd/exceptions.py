"""Library exceptions."""


class PyiCloudException(Exception):
    """Generic iCloud exception."""
    pass


# API
class PyiCloudAPIResponseException(PyiCloudException):
    """iCloud response exception."""
    def __init__(self, reason, code=None, retry=False):
        self.reason = reason
        self.code = code
        message = reason or ""
        if code:
            message += " (%s)" % code
        if retry:
            message += ". Retrying ..."

        super().__init__(message)


class PyiCloudServiceNotActivatedException(PyiCloudAPIResponseException):
    """iCloud service not activated exception."""
    pass


# Login
class PyiCloudFailedLoginException(PyiCloudException):
    """iCloud failed login exception."""
    pass


class PyiCloud2SARequiredException(PyiCloudException):
    """iCloud 2SA required exception."""
    def __init__(self, apple_id):
        message = "Two-step authentication required for account: %s" % apple_id
        super().__init__(message)


class PyiCloudNoStoredPasswordAvailableException(PyiCloudException):
    """iCloud no stored password exception."""
    pass


# Webservice specific
class PyiCloudNoDevicesException(PyiCloudException):
    """iCloud no device exception."""
    pass
