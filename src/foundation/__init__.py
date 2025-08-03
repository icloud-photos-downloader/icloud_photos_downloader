import datetime
import json
from functools import partial
from http.cookiejar import Cookie
from http.cookies import SimpleCookie
from operator import eq, is_, not_
from typing import Any, Callable, Iterable, Mapping, NamedTuple, Tuple, TypeVar

import pytz
from requests import PreparedRequest, Response
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

is_None = partial(is_, None)


is_not_none = compose(not_, is_None)

empty_pairs: Callable[[Iterable[Tuple[T_in, T_out]]], Iterable[Tuple[T_in, T_out]]] = partial(
    filter, compose(is_None, snd)
)
keys_from_pairs: Callable[[Iterable[Tuple[T_in, T_out]]], Iterable[T_in]] = partial(map, fst)
keys_for_empty_values: Callable[[Iterable[Tuple[T_in, T_out]]], Iterable[T_in]] = compose(
    keys_from_pairs, empty_pairs
)

non_empty_pairs: Callable[[Iterable[Tuple[T_in, T_out | None]]], Iterable[Tuple[T_in, T_out]]] = (
    partial(filter, compose(is_not_none, snd))
)


def cookie_to_pair(cookie: Cookie) -> Tuple[str, str | None]:
    return (
        cookie.name,
        cookie.value,
    )


jar_to_pairs: Callable[[Iterable[Cookie]], Iterable[Tuple[str, str]]] = compose(
    non_empty_pairs, partial(map, cookie_to_pair)
)


def cookie_str_to_dict(cookie_header: str) -> Mapping[str, str]:
    """replace cookie header with dict object"""
    simple_cookie = SimpleCookie()
    simple_cookie.load(cookie_header)
    cookies = {k: v.value for k, v in simple_cookie.items()}
    return cookies


def flat_dict(input: Iterable[Mapping[T_in, T_out]]) -> Mapping[T_in, T_out]:
    flattened_dict: dict[T_in, T_out] = {}
    for d in input:
        flattened_dict.update(d)
    return flattened_dict


def response_body(response: Response) -> Any:
    try:
        return response.json()
    except Exception:
        return response.text


def request_body(request: PreparedRequest) -> Any:
    if request.body is not None:
        try:
            return json.loads(request.body)  # ignore: type
        except Exception:
            pass
    return request.body


def response_to_har(response: Response) -> Mapping[str, Any]:
    # headers
    # converted_pairs = map(xxx)

    # cookies from request header
    is_request_cookie = partial(eq, "Cookie")
    is_not_request_cookie = compose(not_, partial(eq, "Cookie"))
    cookie_headers: Callable[[Iterable[Tuple[str, str]]], Iterable[Tuple[str, str]]] = partial(
        filter, compose(is_request_cookie, fst)
    )
    not_request_cookie_headers: Callable[[Iterable[Tuple[str, str]]], Iterable[Tuple[str, str]]] = (
        partial(filter, compose(is_not_request_cookie, fst))
    )
    cookie_header_strings: Callable[[Iterable[Tuple[str, str]]], Iterable[str]] = compose(
        partial(map, snd), cookie_headers
    )
    cookie_maps = compose(partial(map, cookie_str_to_dict), cookie_header_strings)
    extract_response_request_cookies = compose(flat_dict, cookie_maps)

    is_not_response_cookie = compose(not_, partial(eq, "Set-Cookie"))
    not_response_cookie_headers: Callable[
        [Iterable[Tuple[str, str]]], Iterable[Tuple[str, str]]
    ] = partial(filter, compose(is_not_response_cookie, fst))

    return {
        "request": {
            "url": response.request.url,
            "headers": dict(not_request_cookie_headers(response.request.headers.items())),
            "cookies": extract_response_request_cookies(response.request.headers.items()),
            "body": request_body(response.request),
        },
        "response": {
            "status_code": response.status_code,
            "headers": dict(not_response_cookie_headers(response.headers.items())),
            "cookies": dict(jar_to_pairs(response.cookies)),
            "body": response_body(response),
        },
    }
