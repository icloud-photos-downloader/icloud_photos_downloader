import datetime
from typing import Callable, NamedTuple, TypeVar

import pytz
from tzlocal import get_localzone


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
    ts = datetime.datetime.fromtimestamp(vi.commit_timestamp, tz=pytz.utc).astimezone(
        get_localzone()
    )
    return f"version:{vi.version}, commit sha:{vi.commit_sha}, commit timestamp:{ts:%c %Z}"


def bytes_decode(encoding: str) -> Callable[[bytes], str]:
    def _internal(inp: bytes) -> str:
        return inp.decode(encoding)

    return _internal


T_in = TypeVar("T_in")
T_out = TypeVar("T_out")


def wrap_param_in_exception(func: Callable[[T_in], T_out]) -> Callable[[T_in], T_out]:
    """Decorator to wrap excpetion into ValueError with the dump of the input parameter"""

    def _internal(input: T_in) -> T_out:
        try:
            return func(input)
        except Exception as err:
            raise ValueError(f"Invalid Input: {input!r}") from err

    return _internal
