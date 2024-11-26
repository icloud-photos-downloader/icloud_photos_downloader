import subprocess
from icloudpd.notifier import Notifier


class ScriptNotifier(Notifier):
    def __init__(self, script: str) -> None:
        self.script = script

    def send_notification(self, message: str, title: str | None = None) -> None:
        subprocess.run([self.script])