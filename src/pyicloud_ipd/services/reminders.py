"""Reminders service."""
from datetime import datetime
import time
import uuid
import json

from tzlocal import get_localzone_name


class RemindersService:
    """The 'Reminders' iCloud service."""

    def __init__(self, service_root, session, params):
        self.session = session
        self._params = params
        self._service_root = service_root

        self.lists = {}
        self.collections = {}

        self.refresh()

    def refresh(self):
        """Refresh data."""
        params_reminders = dict(self._params)
        params_reminders.update(
            {"clientVersion": "4.0", "lang": "en-us", "usertz": get_localzone_name()}
        )

        # Open reminders
        req = self.session.get(
            self._service_root + "/rd/startup", params=params_reminders
        )

        data = req.json()

        self.lists = {}
        self.collections = {}
        for collection in data["Collections"]:
            temp = []
            self.collections[collection["title"]] = {
                "guid": collection["guid"],
                "ctag": collection["ctag"],
            }
            for reminder in data["Reminders"]:

                if reminder["pGuid"] != collection["guid"]:
                    continue

                if reminder.get("dueDate"):
                    due = datetime(
                        reminder["dueDate"][1],
                        reminder["dueDate"][2],
                        reminder["dueDate"][3],
                        reminder["dueDate"][4],
                        reminder["dueDate"][5],
                    )
                else:
                    due = None

                temp.append(
                    {
                        "title": reminder["title"],
                        "desc": reminder.get("description"),
                        "due": due,
                    }
                )
            self.lists[collection["title"]] = temp

    def post(self, title, description="", collection=None, due_date=None):
        """Adds a new reminder."""
        pguid = "tasks"
        if collection:
            if collection in self.collections:
                pguid = self.collections[collection]["guid"]

        params_reminders = dict(self._params)
        params_reminders.update(
            {"clientVersion": "4.0", "lang": "en-us", "usertz": get_localzone_name()}
        )

        due_dates = None
        if due_date:
            due_dates = [
                int(str(due_date.year) + str(due_date.month) + str(due_date.day)),
                due_date.year,
                due_date.month,
                due_date.day,
                due_date.hour,
                due_date.minute,
            ]

        req = self.session.post(
            self._service_root + "/rd/reminders/tasks",
            data=json.dumps(
                {
                    "Reminders": {
                        "title": title,
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
                        "dueDate": due_dates,
                        "dueDateIsAllDay": False,
                        "lastModifiedDate": None,
                        "createdDate": None,
                        "isFamily": None,
                        "createdDateExtended": int(time.time() * 1000),
                        "guid": str(uuid.uuid4()),
                    },
                    "ClientState": {"Collections": list(self.collections.values())},
                }
            ),
            params=params_reminders,
        )
        return req.ok
