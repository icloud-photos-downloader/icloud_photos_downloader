from typing import Callable, TypeVar

_Tin = TypeVar("_Tin")
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


def apply(input: _Tin) -> Callable[[Callable[[_Tin], _Tout]], _Tout]:
    """
    Applying a function. Equiv curried `($)` in Haskel
    a -> (a -> b) -> b

    Example usage: map(apply(3), [f1,f2,f3]) == [f1(3), f2(3), f3(3)]
    """

    def _intern(func: Callable[[_Tin], _Tout]) -> _Tout:
        return func(input)

    return _intern
