"""Boolean predicate composition utilities for functional programming"""

from typing import Callable, TypeVar

T = TypeVar("T")


def and_(f1: Callable[[T], bool], f2: Callable[[T], bool]) -> Callable[[T], bool]:
    """Logical AND composition of predicates

    >>> is_positive = lambda x: x > 0
    >>> is_even = lambda x: x % 2 == 0
    >>> is_positive_and_even = and_(is_positive, is_even)
    >>> is_positive_and_even(4)
    True
    >>> is_positive_and_even(-2)
    False
    >>> is_positive_and_even(3)
    False
    """
    return lambda x: f1(x) and f2(x)


def or_(f1: Callable[[T], bool], f2: Callable[[T], bool]) -> Callable[[T], bool]:
    """Logical OR composition of predicates

    >>> is_negative = lambda x: x < 0
    >>> is_zero = lambda x: x == 0
    >>> is_not_positive = or_(is_negative, is_zero)
    >>> is_not_positive(-1)
    True
    >>> is_not_positive(0)
    True
    >>> is_not_positive(1)
    False
    """
    return lambda x: f1(x) or f2(x)


def not_(f: Callable[[T], bool]) -> Callable[[T], bool]:
    """Logical NOT of a predicate

    >>> is_positive = lambda x: x > 0
    >>> is_not_positive = not_(is_positive)
    >>> is_not_positive(-1)
    True
    >>> is_not_positive(1)
    False
    """
    return lambda x: not f(x)


def xor_(f1: Callable[[T], bool], f2: Callable[[T], bool]) -> Callable[[T], bool]:
    """Logical XOR composition of predicates

    >>> is_odd = lambda x: x % 2 == 1
    >>> is_positive = lambda x: x > 0
    >>> is_odd_xor_positive = xor_(is_odd, is_positive)
    >>> is_odd_xor_positive(1)  # odd and positive
    False
    >>> is_odd_xor_positive(-3)  # odd but not positive
    True
    >>> is_odd_xor_positive(2)  # positive but not odd
    True
    """
    return lambda x: f1(x) != f2(x)


def always_true(_: T) -> bool:
    """Predicate that always returns True

    >>> always_true(42)
    True
    >>> always_true("anything")
    True
    """
    return True


def always_false(_: T) -> bool:
    """Predicate that always returns False

    >>> always_false(42)
    False
    >>> always_false("anything")
    False
    """
    return False


def eq_pred(expected: T) -> Callable[[T], bool]:
    """Equality predicate generator

    >>> is_five = eq_pred(5)
    >>> is_five(5)
    True
    >>> is_five(3)
    False
    """
    return lambda actual: actual == expected


def ne_pred(expected: T) -> Callable[[T], bool]:
    """Not equal predicate generator

    >>> is_not_five = ne_pred(5)
    >>> is_not_five(3)
    True
    >>> is_not_five(5)
    False
    """
    return lambda actual: actual != expected


def in_pred(container: list[T] | set[T] | tuple[T, ...]) -> Callable[[T], bool]:
    """Membership predicate generator

    >>> is_vowel = in_pred(["a", "e", "i", "o", "u"])
    >>> is_vowel("a")
    True
    >>> is_vowel("b")
    False
    """
    return lambda item: item in container


def not_in_pred(container: list[T] | set[T] | tuple[T, ...]) -> Callable[[T], bool]:
    """Not in membership predicate generator

    >>> is_consonant = not_in_pred(["a", "e", "i", "o", "u"])
    >>> is_consonant("b")
    True
    >>> is_consonant("a")
    False
    """
    return lambda item: item not in container
