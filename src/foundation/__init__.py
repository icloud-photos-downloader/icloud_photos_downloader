import datetime
from functools import partial
from operator import is_, not_
from typing import Callable, Iterable, Mapping, NamedTuple, Tuple, TypeVar

import pytz
from tzlocal import get_localzone

from foundation.core import compose, fst, snd


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
    return f"version:{vi.version}, commit sha:{vi.commit_sha}, commit timestamp:{ts:%c %Z}".replace(
        "  ", " "
    )


def bytes_decode(encoding: str) -> Callable[[bytes], str]:
    def _internal(inp: bytes) -> str:
        return inp.decode(encoding)

    return _internal


T_in = TypeVar("T_in")
T_out = TypeVar("T_out")


def wrap_param_in_exception(caption: str, func: Callable[[T_in], T_out]) -> Callable[[T_in], T_out]:
    """Decorator to wrap excpetion into ValueError with the dump of the input parameter"""

    def _internal(input: T_in) -> T_out:
        try:
            return func(input)
        except Exception as err:
            raise ValueError(f"Invalid Input ({caption}): {input!r}") from err

    return _internal


# def is_none(input: T_in | None) -> bool:
#     return input is None

is_none = partial(is_, None)


is_not_none = compose(not_, is_none)

empty_pairs: Callable[[Iterable[Tuple[T_in, T_out]]], Iterable[Tuple[T_in, T_out]]] = partial(
    filter, compose(is_none, snd)
)
keys_from_pairs: Callable[[Iterable[Tuple[T_in, T_out]]], Iterable[T_in]] = partial(map, fst)
keys_for_empty_values: Callable[[Iterable[Tuple[T_in, T_out]]], Iterable[T_in]] = compose(
    keys_from_pairs, empty_pairs
)

non_empty_pairs: Callable[[Iterable[Tuple[T_in, T_out | None]]], Iterable[Tuple[T_in, T_out]]] = (
    partial(filter, compose(is_not_none, snd))
)


def flat_dict(input: Iterable[Mapping[T_in, T_out]]) -> Mapping[T_in, T_out]:
    flattened_dict: dict[T_in, T_out] = {}
    for d in input:
        flattened_dict.update(d)
    return flattened_dict
