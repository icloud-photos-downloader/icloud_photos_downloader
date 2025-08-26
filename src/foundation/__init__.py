import datetime
from functools import partial
from operator import is_, not_
from typing import (
    Callable,
    Container,
    Iterable,
    List,
    Mapping,
    NamedTuple,
    Sequence,
    Tuple,
    TypeVar,
)

import pytz
from tzlocal import get_localzone

from foundation.core import compose, flip, fst, map_, partial_1_1, snd


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


_T = TypeVar("_T")
_T2 = TypeVar("_T2")


def split_with_alternatives(splitter: Container[_T], inp: Iterable[_T]) -> Sequence[Sequence[_T]]:
    """Breaks incoming sequence into subsequences based on supplied slitter. Splitter is supported as sequence of alternatives.
    >>> split_with_alternatives([2, 4], [1, 2, 3, 2, 5, 4, 6])
    [[1], [2, 3], [2, 5], [4, 6]]
    """
    result: List[List[_T]] = [[]]
    for item in inp:
        if item in splitter:
            #  add group
            result.append([])
        else:
            pass
        group_index = len(result) - 1
        result[group_index].append(item)
    return result


def two_tuple(k: _T, v: _T2) -> Tuple[_T, _T2]:
    """Converts two positional arguments into tuple
    >>> two_tuple(1, 2)
    (1, 2)
    """
    return (k, v)


def unique_sequence(inp: Iterable[_T]) -> Sequence[_T]:
    """Unique values from iterable
    >>> unique_sequence(["abc", "def", "abc", "ghi"])
    ['abc', 'def', 'ghi']
    >>> unique_sequence([1, 2, 1, 3])
    [1, 2, 3]
    """
    to_kv = partial_1_1(map_, partial_1_1(flip(two_tuple), None))
    to_dict: Callable[[Iterable[_T]], Mapping[_T, None]] = compose(dict, to_kv)
    return list(to_dict(inp).keys())
