# mypy: ignore-errors
from __future__ import absolute_import
from datetime import datetime, timedelta
import time
import uuid
import json

from tzlocal import get_localzone


class RemindersService(object):
    def __init__(self, service_root, session, params):
        self.session = session
        self.params = params
        self._service_root = service_root
        self.lists = {}
        self.collections = {}

        self.refresh()

    def refresh(self):
        params_reminders = dict(self.params)
        params_reminders.update({
            'clientVersion': '4.0',
            'lang': 'en-us',
            'usertz': get_localzone().zone
        })

        # Open reminders
        req = self.session.get(
            self._service_root + '/rd/startup',
            params=params_reminders
        )

        startup = req.json()

        self.lists = {}
        self.collections = {}
        for collection in startup['Collections']:
            temp = []
            self.collections[collection['title']] = {
                'guid': collection['guid'],
                'ctag': collection['ctag']
            }
            for reminder in startup['Reminders']:

                if reminder['pGuid'] != collection['guid']:
                    continue
                if 'dueDate' in reminder:
                    if reminder['dueDate']:
                        due = datetime(
                            reminder['dueDate'][1],
                            reminder['dueDate'][2], reminder['dueDate'][3],
                            reminder['dueDate'][4], reminder['dueDate'][5]
                        )
                    else:
                        due = None
                else:
                    due = None
                if reminder['description']:
                    desc = reminder['description']
                else:
                    desc = ""
                temp.append({
                    "title": reminder['title'],
                    "desc": desc,
                    "due": due
                })
            self.lists[collection['title']] = temp

    def post(self, title, description="", collection=None, dueDate=None):
        pguid = 'tasks'
        if collection:
            if collection in self.collections:
                pguid = self.collections[collection]['guid']

        params_reminders = dict(self.params)
        params_reminders.update({
            'clientVersion': '4.0',
            'lang': 'en-us',
            'usertz': get_localzone().zone
        })

        dueDateList = None
        if dueDate:
            dueDateList = [
                int(str(dueDate.year) + str(dueDate.month) + str(dueDate.day)),
                dueDate.year,
                dueDate.month,
                dueDate.day,
                dueDate.hour,
                dueDate.minute
            ]

        req = self.session.post(
            self._service_root + '/rd/reminders/tasks',
            data=json.dumps({
                "Reminders": {
                    'title': title,
                    "description": description,
                    "pGuid": pguid,
                    "etag": None,
                    "order": None,
                    "priority": 0,
                    "recurrence": None,
                    "alarms": [],
                    "startDate": None,
                    "startDateTz": None,
                    "startDateIsAllDay": False,
                    "completedDate": None,
                    "dueDate": dueDateList,
                    "dueDateIsAllDay": False,
                    "lastModifiedDate": None,
                    "createdDate": None,
                    "isFamily": None,
                    "createdDateExtended": int(time.time()*1000),
                    "guid": str(uuid.uuid4())
                },
                "ClientState": {"Collections": list(self.collections.values())}
            }),
            params=params_reminders)
        return req.ok
