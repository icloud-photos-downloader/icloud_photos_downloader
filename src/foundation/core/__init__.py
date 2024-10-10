from typing import Callable, Tuple, TypeVar

_Tin = TypeVar("_Tin")
_Tin2 = TypeVar("_Tin2")
_Tin3 = TypeVar("_Tin3")
_Tout = TypeVar("_Tout")
_Tinter = TypeVar("_Tinter")


def compose(f: Callable[[_Tinter], _Tout], g: Callable[[_Tin], _Tinter]) -> Callable[[_Tin], _Tout]:
    """
    `f after g` composition of functions

    Equiv: lamdba x -> f(g(x))
    """

    def inter_(value: _Tin) -> _Tout:
        return f(g(value))

    return inter_


def identity(value: _Tin) -> _Tin:
    """
    identity function
    """
    return value


def constant(value: _Tout) -> Callable[[_Tin], _Tout]:
    """
    constant function
    """

    def _intern(_: _Tin) -> _Tout:
        return value

    return _intern


def pipe(f: Callable[[_Tin], _Tinter], g: Callable[[_Tinter], _Tout]) -> Callable[[_Tin], _Tout]:
    """
    `g after f` composition of functions (reverse of compose)
    """
    return compose(g, f)


def apply_reverse(input: _Tin) -> Callable[[Callable[[_Tin], _Tout]], _Tout]:
    """
    Applying a function. Equiv curried `(&)` in Haskel
    a -> (a -> b) -> b

    Example usage:

        >>> def _mul(a: int, b: int) -> int:
        ...     return a * b
        >>> def _add(a: int, b: int) -> int:
        ...     return a + b
        >>> list(map(apply_reverse(3), [curry2(_mul)(2), curry2(_add)(5)])) == [6, 8]
        True

    """

    def _intern(func: Callable[[_Tin], _Tout]) -> _Tout:
        return func(input)

    return _intern


def curry2(
    func: Callable[[_Tin, _Tin2], _Tout],
) -> Callable[[_Tin], Callable[[_Tin2], _Tout]]:
    """
    Transforms 2-param function into two nested 1-param functions

    >>> def _mul(a: int, b: int) -> int:
    ...     return a * b
    >>> _mul(2, 3) == 6
    True
    >>> curry2(_mul)(2)(3) == 6
    True

    """

    def _intern(input: _Tin) -> Callable[[_Tin2], _Tout]:
        def _intern2(input2: _Tin2) -> _Tout:
            return func(input, input2)

        return _intern2

    return _intern


def uncurry2(
    func: Callable[[_Tin], Callable[[_Tin2], _Tout]],
) -> Callable[[_Tin, _Tin2], _Tout]:
    """
    Transforms two nested 1-param functions into one 2-param function

    >>> def _mul_c(a: int):
    ...     def _intern(b: int) -> int:
    ...         return a * b
    ...
    ...     return _intern
    >>> _mul_c(2)(3) == 6
    True
    >>> uncurry2(_mul_c)(2, 3) == 6
    True

    """

    def _intern(input: _Tin, input2: _Tin2) -> _Tout:
        return func(input)(input2)

    return _intern


def curry3(
    func: Callable[[_Tin, _Tin2, _Tin3], _Tout],
) -> Callable[[_Tin], Callable[[_Tin2], Callable[[_Tin3], _Tout]]]:
    def _intern(input: _Tin) -> Callable[[_Tin2], Callable[[_Tin3], _Tout]]:
        def _intern2(input2: _Tin2) -> Callable[[_Tin3], _Tout]:
            def _intern3(input3: _Tin3) -> _Tout:
                return func(input, input2, input3)

            return _intern3

        return _intern2

    return _intern


def fst(t: Tuple[_Tin, _Tin2]) -> _Tin:
    """get first of tuple
    >>> fst((1, 2)) == 1
    True
    """
    return t[0]


def snd(t: Tuple[_Tin, _Tin2]) -> _Tin2:
    """get second of tuple
    >>> snd((1, 2)) == 2
    True
    """
    return t[1]
