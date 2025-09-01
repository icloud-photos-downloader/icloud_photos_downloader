import json
from functools import partial
from http.cookiejar import Cookie
from http.cookies import SimpleCookie
from operator import eq, not_
from typing import Any, Callable, Iterable, Mapping, Tuple

from requests import PreparedRequest, Response

from foundation import flat_dict, non_empty_pairs
from foundation.core import compose, fst, snd


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


def is_streaming_response(response: Response) -> bool:
    """Check if response was created with stream=True"""
    try:
        return hasattr(response, "raw") and not response.raw.isclosed()
    except Exception:
        return False


def response_body(response: Response) -> Any:
    if is_streaming_response(response):
        return None
    else:
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


def response_to_har_entry(response: Response) -> Mapping[str, Any]:
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
            "method": response.request.method,
            "url": response.request.url,
            "headers": dict(not_request_cookie_headers(response.request.headers.items())),
            "cookies": extract_response_request_cookies(response.request.headers.items()),
            "content": request_body(response.request),
        },
        "response": {
            "status_code": response.status_code,
            "headers": dict(not_response_cookie_headers(response.headers.items())),
            "cookies": dict(jar_to_pairs(response.cookies)),
            "content": response_body(response),
        },
    }
