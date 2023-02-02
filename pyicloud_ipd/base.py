import six
import uuid
import hashlib
import inspect
import json
import logging
import requests
import sys
import tempfile
import os
from re import match

from pyicloud_ipd.exceptions import (
    PyiCloudFailedLoginException,
    PyiCloudAPIResponseError,
    PyiCloud2SARequiredError,
    PyiCloudServiceNotActivatedErrror
)
from pyicloud_ipd.services import (
    FindMyiPhoneServiceManager,
    CalendarService,
    UbiquityService,
    ContactsService,
    RemindersService,
    PhotosService,
    AccountService
)
from pyicloud_ipd.utils import get_password_from_keyring

if six.PY3:
    import http.cookiejar as cookielib
else:
    import cookielib


logger = logging.getLogger(__name__)


class PyiCloudPasswordFilter(logging.Filter):
    def __init__(self, password):
        self.password = password

    def filter(self, record):
        message = record.getMessage()
        if self.password in message:
            record.msg = message.replace(self.password, "*" * 8)
            record.args = []

        return True


class PyiCloudSession(requests.Session):
    def __init__(self, service):
        self.service = service
        super(PyiCloudSession, self).__init__()

    def request(self, *args, **kwargs):

        # Charge logging to the right service endpoint
        callee = inspect.stack()[2]
        module = inspect.getmodule(callee[0])
        logger = logging.getLogger(module.__name__).getChild('http')
        if self.service._password_filter not in logger.filters:
            logger.addFilter(self.service._password_filter)

        logger.debug("%s %s %s", args[0], args[1], kwargs.get('data', ''))

        response = super(PyiCloudSession, self).request(*args, **kwargs)

        content_type = response.headers.get('Content-Type', '').split(';')[0]
        json_mimetypes = ['application/json', 'text/json']

        if not response.ok and content_type not in json_mimetypes:
            self._raise_error(response.status_code, response.reason)

        if content_type not in json_mimetypes:
            return response

        try:
            json = response.json()
        except:
            logger.warning('Failed to parse response with JSON mimetype')
            return response

        logger.debug(json)

        reason = json.get('errorMessage')
        reason = reason or json.get('reason')
        reason = reason or json.get('errorReason')
        if not reason and isinstance(json.get('error'), six.string_types):
            reason = json.get('error')
        if not reason and json.get('error'):
            reason = "Unknown reason"

        code = json.get('errorCode')
        if not code and json.get('serverErrorCode'):
            code = json.get('serverErrorCode')

        if reason:
            self._raise_error(code, reason)

        return response

    def _raise_error(self, code, reason):
        if self.service.requires_2sa and \
                reason == 'Missing X-APPLE-WEBAUTH-TOKEN cookie':
            raise PyiCloud2SARequiredError(response.url)
        if code == 'ZONE_NOT_FOUND' or code == 'AUTHENTICATION_FAILED':
            reason = 'Please log into https://icloud.com/ to manually ' \
                'finish setting up your iCloud service'
            api_error = PyiCloudServiceNotActivatedErrror(reason, code)
            logger.error(api_error)

            raise(api_error)
        if code == 'ACCESS_DENIED':
            reason = reason + '.  Please wait a few minutes then try ' \
                'again.  The remote servers might be trying to ' \
                'throttle requests.'

        api_error = PyiCloudAPIResponseError(reason, code)
        logger.error(api_error)
        raise api_error


class PyiCloudService(object):
    """
    A base authentication class for the iCloud service. Handles the
    authentication required to access iCloud services.

    Usage:
        from pyicloud_ipd import PyiCloudService
        pyicloud = PyiCloudService('username@apple.com', 'password')
        pyicloud_ipd.iphone.location()
    """

    def __init__(
        self, apple_id, password=None, cookie_directory=None, verify=True,
        client_id=None
    ):
        if password is None:
            password = get_password_from_keyring(apple_id)

        self.data = {}
        self.client_id = client_id or str(uuid.uuid1()).upper()
        self.user = {'apple_id': apple_id, 'password': password}

        self._password_filter = PyiCloudPasswordFilter(password)
        logger.addFilter(self._password_filter)

        self._home_endpoint = 'https://www.icloud.com'
        self._setup_endpoint = 'https://setup.icloud.com/setup/ws/1'

        self._base_login_url = '%s/login' % self._setup_endpoint

        if cookie_directory:
            self._cookie_directory = os.path.expanduser(
                os.path.normpath(cookie_directory)
            )
        else:
            self._cookie_directory = os.path.join(
                tempfile.gettempdir(),
                'pyicloud',
            )

        self.session = PyiCloudSession(self)
        self.session.verify = verify
        self.session.headers.update({
            'Origin': self._home_endpoint,
            'Referer': '%s/' % self._home_endpoint,
            'User-Agent': 'Opera/9.52 (X11; Linux i686; U; en)'
        })

        cookiejar_path = self._get_cookiejar_path()
        self.session.cookies = cookielib.LWPCookieJar(filename=cookiejar_path)
        if os.path.exists(cookiejar_path):
            try:
                self.session.cookies.load()
                logger.debug("Read cookies from %s", cookiejar_path)
            except:
                # Most likely a pickled cookiejar from earlier versions.
                # The cookiejar will get replaced with a valid one after
                # successful authentication.
                logger.warning("Failed to read cookiejar %s", cookiejar_path)

        self.params = {
            'clientBuildNumber': '17DHotfix5',
            'clientMasteringNumber': '17DHotfix5',
            'ckjsBuildVersion': '17DProjectDev77',
            'ckjsVersion': '2.0.5',
            'clientId': self.client_id,
        }

        self.authenticate()

    def authenticate(self):
        """
        Handles authentication, and persists the X-APPLE-WEB-KB cookie so that
        subsequent logins will not cause additional e-mails from Apple.
        """

        logger.info("Authenticating as %s", self.user['apple_id'])

        data = dict(self.user)

        # We authenticate every time, so "remember me" is not needed
        data.update({'extended_login': False})

        try:
            req = self.session.post(
                self._base_login_url,
                params=self.params,
                data=json.dumps(data)
            )
        except PyiCloudAPIResponseError as error:
            msg = 'Invalid email/password combination.'
            raise PyiCloudFailedLoginException(msg, error)

        resp = req.json()
        self.params.update({'dsid': resp['dsInfo']['dsid']})

        if not os.path.exists(self._cookie_directory):
            os.mkdir(self._cookie_directory)
        self.session.cookies.save()
        logger.debug("Cookies saved to %s", self._get_cookiejar_path())

        self.data = resp
        self.webservices = self.data['webservices']

        logger.info("Authentication completed successfully")
        logger.debug(self.params)

    def _get_cookiejar_path(self):
        # Get path for cookiejar file
        return os.path.join(
            self._cookie_directory,
            ''.join([c for c in self.user.get('apple_id') if match(r'\w', c)])
        )

    @property
    def requires_2sa(self):
        """ Returns True if two-step authentication is required."""
        return self.data.get('hsaChallengeRequired', False) \
            and self.data['dsInfo'].get('hsaVersion', 0) >= 1
        # FIXME: Implement 2FA for hsaVersion == 2

    @property
    def trusted_devices(self):
        """ Returns devices trusted for two-step authentication."""
        request = self.session.get(
            '%s/listDevices' % self._setup_endpoint,
            params=self.params
        )
        return request.json().get('devices')

    def send_verification_code(self, device):
        """ Requests that a verification code is sent to the given device"""
        data = json.dumps(device)
        request = self.session.post(
            '%s/sendVerificationCode' % self._setup_endpoint,
            params=self.params,
            data=data
        )
        return request.json().get('success', False)

    def validate_verification_code(self, device, code):
        """ Verifies a verification code received on a trusted device"""
        device.update({
            'verificationCode': code,
            'trustBrowser': True
        })
        data = json.dumps(device)

        try:
            request = self.session.post(
                '%s/validateVerificationCode' % self._setup_endpoint,
                params=self.params,
                data=data
            )
        except PyiCloudAPIResponseError as error:
            if error.code == -21669:
                # Wrong verification code
                return False
            raise

        # Re-authenticate, which will both update the HSA data, and
        # ensure that we save the X-APPLE-WEBAUTH-HSA-TRUST cookie.
        self.authenticate()

        return not self.requires_2sa

    @property
    def devices(self):
        """ Return all devices."""
        service_root = self.webservices['findme']['url']
        return FindMyiPhoneServiceManager(
            service_root,
            self.session,
            self.params
        )

    @property
    def account(self):
        service_root = self.webservices['account']['url']
        return AccountService(
            service_root,
            self.session,
            self.params
        )

    @property
    def iphone(self):
        return self.devices[0]

    @property
    def files(self):
        if not hasattr(self, '_files'):
            service_root = self.webservices['ubiquity']['url']
            self._files = UbiquityService(
                service_root,
                self.session,
                self.params
            )
        return self._files

    @property
    def photos(self):
        if not hasattr(self, '_photos'):
            service_root = self.webservices['ckdatabasews']['url']
            self._photos = PhotosService(
                service_root,
                self.session,
                self.params
            )
        return self._photos

    @property
    def calendar(self):
        service_root = self.webservices['calendar']['url']
        return CalendarService(service_root, self.session, self.params)

    @property
    def contacts(self):
        service_root = self.webservices['contacts']['url']
        return ContactsService(service_root, self.session, self.params)

    @property
    def reminders(self):
        service_root = self.webservices['reminders']['url']
        return RemindersService(service_root, self.session, self.params)

    def __unicode__(self):
        return 'iCloud API: %s' % self.user.get('apple_id')

    def __str__(self):
        as_unicode = self.__unicode__()
        if sys.version_info[0] >= 3:
            return as_unicode
        else:
            return as_unicode.encode('ascii', 'ignore')

    def __repr__(self):
        return '<%s>' % str(self)
