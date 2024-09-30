from typing import Callable, Tuple, TypeVar

_T_contra = TypeVar("_T_contra", contravariant=True)
_T2_contra = TypeVar("_T2_contra", contravariant=True)
_T3_contra = TypeVar("_T3_contra", contravariant=True)
_T_co = TypeVar("_T_co", covariant=True)
_T_inv = TypeVar("_T_inv")


def compose(
    f: Callable[[_T_inv], _T_co], g: Callable[[_T_contra], _T_inv]
) -> Callable[[_T_contra], _T_co]:
    """
    `f after g` composition of functions

    Equiv: lamdba x -> f(g(x))
    """

    def inter_(value: _T_contra) -> _T_co:
        return f(g(value))

    return inter_


def identity(value: _T_inv) -> _T_inv:
    """
    identity function
    """
    return value


def constant(value: _T_inv) -> Callable[[_T_contra], _T_inv]:
    """
    constant function
    """

    def _intern(_: _T_contra) -> _T_inv:
        return value

    return _intern


def pipe(
    f: Callable[[_T_contra], _T_inv], g: Callable[[_T_inv], _T_co]
) -> Callable[[_T_contra], _T_co]:
    """
    `g after f` composition of functions (reverse of compose)
    """
    return compose(g, f)


def apply_reverse(input: _T_contra) -> Callable[[Callable[[_T_contra], _T_co]], _T_co]:
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

    def _intern(func: Callable[[_T_contra], _T_co]) -> _T_co:
        return func(input)

    return _intern


def curry2(
    func: Callable[[_T_contra, _T2_contra], _T_co],
) -> Callable[[_T_contra], Callable[[_T2_contra], _T_co]]:
    """
    Transforms 2-param function into two nested 1-param functions

    >>> def _mul(a: int, b: int) -> int:
    ...     return a * b
    >>> _mul(2, 3) == 6
    True
    >>> curry2(_mul)(2)(3) == 6
    True

    """

    def _intern(input: _T_contra) -> Callable[[_T2_contra], _T_co]:
        def _intern2(input2: _T2_contra) -> _T_co:
            return func(input, input2)

        return _intern2

    return _intern


def uncurry2(
    func: Callable[[_T_contra], Callable[[_T2_contra], _T_co]],
) -> Callable[[_T_contra, _T2_contra], _T_co]:
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

    def _intern(input: _T_contra, input2: _T2_contra) -> _T_co:
        return func(input)(input2)

    return _intern


def curry3(
    func: Callable[[_T_contra, _T2_contra, _T3_contra], _T_co],
) -> Callable[[_T_contra], Callable[[_T2_contra], Callable[[_T3_contra], _T_co]]]:
    def _intern(input: _T_contra) -> Callable[[_T2_contra], Callable[[_T3_contra], _T_co]]:
        def _intern2(input2: _T2_contra) -> Callable[[_T3_contra], _T_co]:
            def _intern3(input3: _T3_contra) -> _T_co:
                return func(input, input2, input3)

            return _intern3

        return _intern2

    return _intern


def fst(t: Tuple[_T_inv, _T2_contra]) -> _T_inv:
    """get first of tuple
    >>> fst((1, 2)) == 1
    True
    """
    return t[0]


def snd(t: Tuple[_T_contra, _T_inv]) -> _T_inv:
    """get second of tuple
    >>> snd((1, 2)) == 2
    True
    """
    return t[1]


def flip(
    func: Callable[[_T_contra, _T2_contra], _T_co],
) -> Callable[[_T2_contra, _T_contra], _T_co]:
    """flips params
    >>> def minus(a: int, b: int) -> int:
    ...     return a - b
    >>> minus(5, 3) == 2
    True
    >>> flip(minus)(5, 3) == -2
    True
    """

    def _intern(input2: _T2_contra, input: _T_contra) -> _T_co:
        return func(input, input2)

    return _intern


def compact2(
    func: Callable[[_T_contra, _T2_contra], _T_co],
) -> Callable[[Tuple[_T_contra, _T2_contra]], _T_co]:
    """Compacts two parameters into one tuple"""

    def _intern(input: Tuple[_T_contra, _T2_contra]) -> _T_co:
        return func(fst(input), snd(input))

    return _intern


def expand2(
    func: Callable[[Tuple[_T_contra, _T2_contra]], _T_co],
) -> Callable[[_T_contra, _T2_contra], _T_co]:
    def _intern(input: _T_contra, input2: _T2_contra) -> _T_co:
        return func((input, input2))

    return _intern


def pipe2(
    f: Callable[[_T_contra, _T2_contra], _T_inv], g: Callable[[_T_inv], _T_co]
) -> Callable[[_T_contra, _T2_contra], _T_co]:
    """
    `g after f` composition of functions (reverse of compose). f takes 2 params
    >>> def mul(a: int, b: int) -> int:
    ...     return a * b
    >>> def add5(a: int) -> int:
    ...     return a + 5
    >>> pipe2(mul, add5)(2, 3) == 11
    True
    """
    return expand2(pipe(compact2(f), g))
