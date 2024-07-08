import time
from typing import NamedTuple


class VersionInfo(NamedTuple):
    version: str
    commit_sha: str
    commit_timestamp: int


# will be updated by CI
version_info = VersionInfo(
    version="0.0.1",
    commit_sha="abcdefgh",
    commit_timestamp=1234567890,
)


def version_info_formatted() -> str:
    vi = version_info
    ts = time.strftime("%c", time.gmtime(vi.commit_timestamp))
    return f"version:{vi.version}, commit sha:{vi.commit_sha}, commit timestamp:{ts} UTC"
