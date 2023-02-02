
class PyiCloudException(Exception):
    pass


class PyiCloudNoDevicesException(PyiCloudException):
    pass


class PyiCloudAPIResponseError(PyiCloudException):
    def __init__(self, reason, code):
        self.reason = reason
        self.code = code
        message = reason
        if code:
            message += " (%s)" % code

        super(PyiCloudAPIResponseError, self).__init__(message)


class PyiCloudFailedLoginException(PyiCloudException):
    pass


class PyiCloud2SARequiredError(PyiCloudException):
    def __init__(self, url):
        message = "Two-step authentication required for %s" % url
        super(PyiCloud2SARequiredError, self).__init__(message)


class PyiCloudNoDevicesException(Exception):
    pass


class NoStoredPasswordAvailable(PyiCloudException):
    pass


class PyiCloudServiceNotActivatedErrror(PyiCloudAPIResponseError):
    pass
