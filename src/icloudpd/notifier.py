from abc import ABC


class Notifier(ABC):
    def send_notification(self,
                          message: str,
                          title: str | None = None) -> None:
        ...