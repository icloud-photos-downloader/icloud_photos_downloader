from __future__ import absolute_import
import os
import uuid
from datetime import datetime
from calendar import monthrange


class ContactsService(object):
    """
    The 'Contacts' iCloud service, connects to iCloud and returns contacts.
    """
    def __init__(self, service_root, session, params):
        self.session = session
        self.params = params
        self._service_root = service_root
        self._contacts_endpoint = '%s/co' % self._service_root
        self._contacts_refresh_url = '%s/startup' % self._contacts_endpoint
        self._contacts_changeset_url = '%s/changeset' % self._contacts_endpoint

    def refresh_client(self, from_dt=None, to_dt=None):
        """
        Refreshes the ContactsService endpoint, ensuring that the
        contacts data is up-to-date.
        """
        params_contacts = dict(self.params)
        params_contacts.update({
            'clientVersion': '2.1',
            'locale': 'en_US',
            'order': 'last,first',
        })
        req = self.session.get(
            self._contacts_refresh_url,
            params=params_contacts
        )
        self.response = req.json()
        params_refresh = dict(self.params)
        params_refresh.update({
            'prefToken': req.json()["prefToken"],
            'syncToken': req.json()["syncToken"],
        })
        self.session.post(self._contacts_changeset_url, params=params_refresh)
        req = self.session.get(
            self._contacts_refresh_url,
            params=params_contacts
        )
        self.response = req.json()

    def all(self):
        """
        Retrieves all contacts.
        """
        self.refresh_client()
        return self.response['contacts']
