from typing import Callable, TypeVar

_Tin = TypeVar("_Tin")
_Tin2 = TypeVar("_Tin2")
_Tin3 = TypeVar("_Tin3")
_Tout = TypeVar("_Tout")


def bind(
    func: Callable[[_Tin], _Tout | None],
) -> Callable[[_Tin | None], _Tout | None]:
    """
    Monadic bind for Optional.

    Example usage:
        >>> def div8(divider: int) -> float | None:
        ...     if divider == 0:
        ...         return None
        ...     return 8 / divider
        >>> b = bind(div8)

        Basic operation on div8:
        >>> div8(2) == 4
        True
        >>> div8(0) == None
        True

        Passing None throws:
        >>> div8(None)
        Traceback (most recent call last):
            ...
        TypeError: unsupported operand type(s) for /: 'int' and 'NoneType'

        Binding works for basic and None:
        >>> b(2) == 4
        True
        >>> b(0) == None
        True
        >>> b(None) == None
        True

    """

    def _intern(input: _Tin | None) -> _Tout | None:
        if input:
            return func(input)
        return None

    return _intern


def lift2(
    func: Callable[[_Tin, _Tin2], _Tout],
) -> Callable[[_Tin | None, _Tin2 | None], _Tout | None]:
    """
    Lifts regular function into Optional. (Lift2 for Optional Applicative Functor)
    (a -> b -> c) -> Maybe a -> Maybe b -> Maybe c

    Example usage:
        >>> def _mul(input: int, input2: int) -> int:
        ...     return input * input2
        >>> l = lift2(_mul)

        Works for numbers:
        >>> l(2, 3) == 6
        True

        Works for None in any and/or all parameter:
        >>> l(2, None) == None
        True
        >>> l(None, 3) == None
        True
        >>> l(None, None) == None
        True

    """

    def _intern(input: _Tin | None, input2: _Tin2 | None) -> _Tout | None:
        if input and input2:
            return func(input, input2)
        return None

    return _intern


def lift3(
    func: Callable[[_Tin, _Tin2, _Tin3], _Tout],
) -> Callable[[_Tin | None, _Tin2 | None, _Tin3 | None], _Tout | None]:
    """
    Lifts regular function into Optional. see lift2 for Optional Applicative Functor
    (a -> b -> c) -> Maybe a -> Maybe b -> Maybe c
    """

    def _intern(input: _Tin | None, input2: _Tin2 | None, input3: _Tin3 | None) -> _Tout | None:
        if input and input2 and input3:
            return func(input, input2, input3)
        return None

    return _intern


def fromMaybe(default: _Tin) -> Callable[[_Tin | None], _Tin]:
    """
    FromMaybe function similar to Haskell's fromMaybe.
    Takes a default value and returns a function that extracts the value from Maybe,
    using the default if the Maybe is None.

    Signature: a -> Maybe a -> a

    Args:
        default: The default value to return when input is None

    Returns:
        A function that takes an optional input and returns the value or default

    Example usage:
        >>> extract_or_zero = fromMaybe(0)
        >>> extract_or_zero(5) == 5
        True
        >>> extract_or_zero(None) == 0
        True
    """

    def _intern(maybe_value: _Tin | None) -> _Tin:
        if maybe_value is not None:
            return maybe_value
        return default

    return _intern
