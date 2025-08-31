import re
from functools import partial, singledispatch
from operator import is_, not_
from typing import Any, Callable, Iterable, Mapping, Sequence, Tuple, TypeVar

from foundation import non_empty_pairs
from foundation.core import compose, flip, fst

T1 = TypeVar("T1")
T2 = TypeVar("T2")

# def extract_context(context: Context[T1], pair: Tuple[T1, T2]) -> Tuple[Context[T1], T2]:
#     return (context + [pair[0]], pair[1])

Context = str


def extract_context(context: Context, pair: Tuple[str, T1]) -> Tuple[Context, T1]:
    from foundation.string_utils import endswith

    should_add_dot = context and not endswith(".")(context)
    new_context = context + ("." if should_add_dot else "") + pair[0]
    return (new_context, pair[1])


Rule = Tuple[re.Pattern[str], Callable[[str], str | None]]


def first(input: Iterable[T1]) -> T1 | StopIteration:
    for item in input:
        return item
    return StopIteration()


def first_or_default(input: Iterable[T1], default: T2) -> T1 | T2:
    for item in input:
        return item
    return default


first_or_none: Callable[[Iterable[T1]], T1 | None] = partial(flip(first_or_default), None)

is_none = partial(is_, None)

is_not_none = compose(not_, is_none)


def first_matching_rule(context: Context, rules: Sequence[Rule]) -> Rule | None:
    match_with_context = partial(flip(re.search), context)
    match_on_key_of_pair = compose(match_with_context, fst)
    is_matching_pair = compose(is_not_none, match_on_key_of_pair)
    filter_pairs: Callable[[Iterable[Rule]], Iterable[Rule]] = partial(filter, is_matching_pair)
    first_matching = compose(first_or_none, filter_pairs)
    first_found = first_matching(rules)
    return first_found


@singledispatch
def _apply_rules_internal(input: Any, context: Context, rules: Sequence[Rule]) -> Any:
    # print(f"ANY {context} {input}")
    return input


@_apply_rules_internal.register(str)
def _(input: str, context: Context, rules: Sequence[Rule]) -> str | None:
    # print(f"STR {context} {input}")
    first_found_rule = first_matching_rule(context, rules)
    if first_found_rule is None:
        # no pattern matched - return unchanged
        return input
    else:
        return first_found_rule[1](input)


@_apply_rules_internal.register(tuple)
def _(input: Tuple[str, Any], context: Context, rules: Sequence[Rule]) -> Any:
    # print(f"TUPLE {context} {input}")
    first_found_rule = first_matching_rule(context, rules)
    if first_found_rule is None:
        # no pattern matched - continue recursive
        new_context, new_value = extract_context(context, input)
        return (input[0], _apply_rules_internal(new_value, new_context, rules))
    else:
        # this is to allow overriding the whole object with string
        return (input[0], first_found_rule[1]("tuple"))


filter_not_none: Callable[[Iterable[T1 | None]], Iterable[T1]] = partial(filter, is_not_none)


def apply_rules(context: Context, rules: Sequence[Rule], input: Any) -> Any:
    return _apply_rules_internal(input, context, rules)


@_apply_rules_internal.register(list)
def _(input: Sequence[Any], context: Context, rules: Sequence[Rule]) -> Any:
    # print(f"LIST {context} {input}")
    first_found_rule = first_matching_rule(context, rules)
    if first_found_rule is None:
        # no pattern matched - continue recursive
        apply_context_rules = partial(apply_rules, context + ".", rules)
        apply_rule_iter = partial(map, apply_context_rules)
        apply_and_filter: Callable[[Iterable[Any]], Iterable[Any]] = compose(
            filter_not_none, apply_rule_iter
        )
        materialized_apply_and_filter: Callable[[Iterable[Any]], Iterable[Any]] = compose(
            list, apply_and_filter
        )
        return materialized_apply_and_filter(input)
    else:
        # this is to allow overriding the whole list with string
        return first_found_rule[1]("list")


@_apply_rules_internal.register(dict)
def _(input: Mapping[str, Any], context: Context, rules: Sequence[Rule]) -> Any:
    # print(f"DICT {context} {input}")
    first_found_rule = first_matching_rule(context, rules)
    if first_found_rule is None:
        # no pattern matched - continue recursive
        apply_context_rules = partial(apply_rules, context, rules)
        apply_rule_iter = partial(map, apply_context_rules)
        apply_and_filter: Callable[[Iterable[Any]], Iterable[Any]] = compose(
            non_empty_pairs, apply_rule_iter
        )
        materialized_apply_and_filter: Callable[[Iterable[Any]], Iterable[Any]] = compose(
            dict, apply_and_filter
        )
        return materialized_apply_and_filter(input.items())
    else:
        # this is to allow overriding the whole list with string
        return first_found_rule[1]("dict")


def re_compile_flag(flags: re.RegexFlag, input: str) -> re.Pattern[str]:
    return re.compile(input, flags)


re_compile_ignorecase: Callable[[str], re.Pattern[str]] = partial(
    re_compile_flag, re.RegexFlag.IGNORECASE
)

compile_patterns: Callable[[Iterable[str]], Iterable[re.Pattern[str]]] = partial(
    map, re_compile_ignorecase
)
