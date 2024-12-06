import requests
from requests.auth import HTTPBasicAuth

from icloudpd.notifier import Notifier


class NtfySender(Notifier):

    def __init__(self,
                 server: str,
                 topic: str,
                 protocol: str = "https",
                 username: str | None = None,
                 password: str | None = None,
                 token: str | None = None,
                 priority: str | None = None,
                 tags: list[str] = [],
                 click: str | None = None,
                 email: str | None = None) -> None:
        self.server = server
        self.topic = topic
        self.protocol = protocol
        self.username = username
        self.password = password
        self.token = token
        self.priority = priority
        self.tags = tags
        self.click = click
        self.email = email
    
    
    def _build_url(self) -> str:
        return f"{self.protocol}://{self.server}/{self.topic}"
    

    def _build_headers(self, title: str | None = None) -> dict[str, str]:
        headers = {}

        if title:
            headers["X-Title"] = title

        if self.priority:
            headers["X-Priority"] = self.priority
        
        if len(self.tags) > 0:
            headers["X-Tags"] = ",".join(self.tags)
        
        if self.click:
            headers["X-Click"] = self.click
        
        if self.email:
            headers["X-Email"] = self.email
        
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        
        return headers
    

    def _build_auth(self) -> None:
        if self.username or self.password:
            return HTTPBasicAuth(self.username, self.password)
        return None
    

    def send_notification(self,
                          message: str,
                          title: str | None = None) -> None:
        response = requests.post(self._build_url(),
                      data=message.encode(encoding='utf-8'),
                      headers=self._build_headers(title),
                      auth=self._build_auth())
        response.raise_for_status()