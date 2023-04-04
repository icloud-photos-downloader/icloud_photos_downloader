import json
import sys

import six

from pyicloud_ipd.exceptions import PyiCloudNoDevicesException


class FindMyiPhoneServiceManager(object):
    """ The 'Find my iPhone' iCloud service

    This connects to iCloud and return phone data including the near-realtime
    latitude and longitude.

    """

    def __init__(self, service_root, session, params):
        self.session = session
        self.params = params
        self._service_root = service_root
        self._fmip_endpoint = '%s/fmipservice/client/web' % self._service_root
        self._fmip_refresh_url = '%s/refreshClient' % self._fmip_endpoint
        self._fmip_sound_url = '%s/playSound' % self._fmip_endpoint
        self._fmip_message_url = '%s/sendMessage' % self._fmip_endpoint
        self._fmip_lost_url = '%s/lostDevice' % self._fmip_endpoint

        self._devices = {}
        self.refresh_client()

    def refresh_client(self):
        """ Refreshes the FindMyiPhoneService endpoint,

        This ensures that the location data is up-to-date.

        """
        req = self.session.post(
            self._fmip_refresh_url,
            params=self.params,
            data=json.dumps(
                {
                    'clientContext': {
                        'fmly': True,
                        'shouldLocate': True,
                        'selectedDevice': 'all',
                    }
                }
            )
        )
        self.response = req.json()

        for device_info in self.response['content']:
            device_id = device_info['id']
            if device_id not in self._devices:
                self._devices[device_id] = AppleDevice(
                    device_info,
                    self.session,
                    self.params,
                    manager=self,
                    sound_url=self._fmip_sound_url,
                    lost_url=self._fmip_lost_url,
                    message_url=self._fmip_message_url,
                )
            else:
                self._devices[device_id].update(device_info)

        if not self._devices:
            raise PyiCloudNoDevicesException()

    def __getitem__(self, key):
        if isinstance(key, int):
            if six.PY3:
                key = list(self.keys())[key]
            else:
                key = self.keys()[key]
        return self._devices[key]

    def __getattr__(self, attr):
        return getattr(self._devices, attr)

    def __unicode__(self):
        return six.text_type(self._devices)

    def __str__(self):
        as_unicode = self.__unicode__()
        if sys.version_info[0] >= 3:
            return as_unicode
        else:
            return as_unicode.encode('ascii', 'ignore')

    def __repr__(self):
        return six.text_type(self)


class AppleDevice(object):
    def __init__(
        self, content, session, params, manager,
        sound_url=None, lost_url=None, message_url=None
    ):
        self.content = content
        self.manager = manager
        self.session = session
        self.params = params

        self.sound_url = sound_url
        self.lost_url = lost_url
        self.message_url = message_url

    def update(self, data):
        self.content = data

    def location(self):
        self.manager.refresh_client()
        return self.content['location']

    def status(self, additional=[]):
        """ Returns status information for device.

        This returns only a subset of possible properties.
        """
        self.manager.refresh_client()
        fields = ['batteryLevel', 'deviceDisplayName', 'deviceStatus', 'name']
        fields += additional
        properties = {}
        for field in fields:
            properties[field] = self.content.get(field)
        return properties

    def play_sound(self, subject='Find My iPhone Alert'):
        """ Send a request to the device to play a sound.

        It's possible to pass a custom message by changing the `subject`.
        """
        data = json.dumps({
            'device': self.content['id'],
            'subject': subject,
            'clientContext': {
                'fmly': True
            }
        })
        self.session.post(
            self.sound_url,
            params=self.params,
            data=data
        )

    def display_message(
        self, subject='Find My iPhone Alert', message="This is a note",
        sounds=False
    ):
        """ Send a request to the device to play a sound.

        It's possible to pass a custom message by changing the `subject`.
        """
        data = json.dumps(
            {
                'device': self.content['id'],
                'subject': subject,
                'sound': sounds,
                'userText': True,
                'text': message
            }
        )
        self.session.post(
            self.message_url,
            params=self.params,
            data=data
        )

    def lost_device(
        self, number,
        text='This iPhone has been lost. Please call me.',
        newpasscode=""
    ):
        """ Send a request to the device to trigger 'lost mode'.

        The device will show the message in `text`, and if a number has
        been passed, then the person holding the device can call
        the number without entering the passcode.
        """
        data = json.dumps({
            'text': text,
            'userText': True,
            'ownerNbr': number,
            'lostModeEnabled': True,
            'trackingEnabled': True,
            'device': self.content['id'],
            'passcode': newpasscode
        })
        self.session.post(
            self.lost_url,
            params=self.params,
            data=data
        )

    @property
    def data(self):
        return self.content

    def __getitem__(self, key):
        return self.content[key]

    def __getattr__(self, attr):
        return getattr(self.content, attr)

    def __unicode__(self):
        display_name = self['deviceDisplayName']
        name = self['name']
        return '%s: %s' % (
            display_name,
            name,
        )

    def __str__(self):
        as_unicode = self.__unicode__()
        if sys.version_info[0] >= 3:
            return as_unicode
        else:
            return as_unicode.encode('ascii', 'ignore')

    def __repr__(self):
        return '<AppleDevice(%s)>' % str(self)
