from typing import Callable, Optional, TypeVar

_Tin = TypeVar("_Tin")
_Tin2 = TypeVar("_Tin2")
_Tin3 = TypeVar("_Tin3")
_Tout = TypeVar("_Tout")


def bind(
    func: Callable[[_Tin], Optional[_Tout]],
) -> Callable[[Optional[_Tin]], Optional[_Tout]]:
    """
    Monadic bind for Optional.

    Example usage:
        def div8(divider: int) -> Optional[float]:
            if divider == 0:
                return None
            return 8 / divider

        b = bind_optional(div8)

        assert div8(2) == 4
        assert div8(0) == None
        assert b(2) == 4
        assert b(0) == None
        assert b(None) == None

    """

    def _intern(input: Optional[_Tin]) -> Optional[_Tout]:
        if input:
            return func(input)
        return None

    return _intern


def lift2(
    func: Callable[[_Tin, _Tin2], _Tout],
) -> Callable[[Optional[_Tin], Optional[_Tin2]], Optional[_Tout]]:
    """
    Lifts regular function into Optional. (Lift2 for Optional Applicative Functor)
    (a -> b -> c) -> Maybe a -> Maybe b -> Maybe c

    Example usage:
        def dbl(x: int) -> int:
            return x * 2
        l = lift2_optional(dbl)
        assert l(2) == 4
        assert l(None) == None

    """

    def _intern(input: Optional[_Tin], input2: Optional[_Tin2]) -> Optional[_Tout]:
        if input and input2:
            return func(input, input2)
        return None

    return _intern


def lift3(
    func: Callable[[_Tin, _Tin2, _Tin3], _Tout],
) -> Callable[[Optional[_Tin], Optional[_Tin2], Optional[_Tin3]], Optional[_Tout]]:
    def _intern(
        input: Optional[_Tin], input2: Optional[_Tin2], input3: Optional[_Tin3]
    ) -> Optional[_Tout]:
        if input and input2 and input3:
            return func(input, input2, input3)
        return None

    return _intern
