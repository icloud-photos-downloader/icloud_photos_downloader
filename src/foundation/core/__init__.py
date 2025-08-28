from itertools import chain, islice, tee, zip_longest
from typing import Callable, Iterable, Tuple, TypeGuard, TypeVar

_T_contra = TypeVar("_T_contra", contravariant=True)
_T2_contra = TypeVar("_T2_contra", contravariant=True)
_T3_contra = TypeVar("_T3_contra", contravariant=True)
_T_co = TypeVar("_T_co", covariant=True)
_T2_co = TypeVar("_T2_co", covariant=True)
_T_inv = TypeVar("_T_inv")
_T2_inv = TypeVar("_T2_inv")


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


def arrow(
    func1: Callable[[_T_contra], _T_co],
    func2: Callable[[_T2_contra], _T2_co],
    inp: Tuple[_T_contra, _T2_contra],
) -> Tuple[_T_co, _T2_co]:
    """applies different functions for elements of the tuple like Control.Arrow ***"""

    return (func1(inp[0]), func2(inp[1]))


def partial_1_1(
    f: Callable[[_T_contra, _T2_contra], _T_co], p1: _T_contra
) -> Callable[[_T2_contra], _T_co]:
    """
    partial application of one parameter. Safe for static type-checking

    Equiv: functools.partial
    """

    def inter_(value: _T2_contra) -> _T_co:
        return f(p1, value)

    return inter_


def partial_2_1(
    f: Callable[[_T_contra, _T2_contra, _T3_contra], _T_co], p1: _T_contra, p2: _T2_contra
) -> Callable[[_T3_contra], _T_co]:
    """
    partial application of one parameter. Safe for static type-checking

    Equiv: functools.partial
    """

    def inter_(value: _T3_contra) -> _T_co:
        return f(p1, p2, value)

    return inter_


def filter_(f: Callable[[_T_contra], bool], p1: Iterable[_T_contra]) -> Iterable[_T_contra]:
    """
    typed filter

    Equiv: functools.filter
    """

    return filter(f, p1)


def filter_guarded(
    f: Callable[[_T_contra], TypeGuard[_T2_contra]], p1: Iterable[_T_contra]
) -> Iterable[_T2_contra]:
    """
    typed filter for guarded output

    Equiv: functools.filter
    """

    return filter(f, p1)


def map_(f: Callable[[_T_contra], _T_co], p1: Iterable[_T_contra]) -> Iterable[_T_co]:
    """
    typed map

    Equiv: functools.map
    """

    return map(f, p1)


def tee_(inp: Iterable[_T_contra]) -> Tuple[Iterable[_T_contra], Iterable[_T_contra]]:
    """
    duplicate iterable
    >>> inp = [1, 2, 3]
    >>> a, b = tee_(inp)
    >>> list(a)
    [1, 2, 3]
    >>> list(b)
    [1, 2, 3]
    """
    result = tee(inp)
    return result[0], result[1]


def zip_longest_(
    inp: Tuple[Iterable[_T_inv], Iterable[_T2_inv]],
) -> Iterable[Tuple[_T_inv | None, _T2_inv | None]]:
    """
    zip tuple of iterables into iterable of tuples
    >>> inp = ([1, 2], [4, 5, 6])
    >>> list(zip_longest_(inp))
    [(1, 4), (2, 5), (None, 6)]
    """
    return zip_longest(inp[0], inp[1])


def unzip(
    inp: Iterable[Tuple[_T_inv, _T2_inv]],
) -> Tuple[Iterable[_T_inv], Iterable[_T2_inv]]:
    """
    unzip iterable of tuples
    >>> a, b = unzip([(1, 2), (3, 4), (5, 6)])
    >>> list(a)
    [1, 3, 5]
    >>> list(b)
    [2, 4, 6]
    """
    fst_i: Callable[[Iterable[Tuple[_T_inv, _T2_inv]]], Iterable[_T_inv]] = partial_1_1(map_, fst)
    snd_i: Callable[[Iterable[Tuple[_T_inv, _T2_inv]]], Iterable[_T2_inv]] = partial_1_1(map_, snd)
    split = partial_2_1(arrow, fst_i, snd_i)
    func = compose(split, tee_)
    return func(inp)


def chain_from_iterable(inp: Iterable[Iterable[_T_inv]]) -> Iterable[_T_inv]:
    return chain.from_iterable(inp)


def skip(inp: int, p1: Iterable[_T_co]) -> Iterable[_T_co]:
    """
    typed islice with start

    Equiv: itertools.islice
    >>> list(skip(3, [1, 2, 3, 4, 5]))
    [4, 5]
    """
    return islice(p1, inp, None)


def take(inp: int, p1: Iterable[_T_co]) -> Iterable[_T_co]:
    """
    typed islice with stop

    Equiv: itertools.islice
    >>> list(take(3, [1, 2, 3, 4, 5]))
    [1, 2, 3]
    """

    return islice(p1, None, inp)
