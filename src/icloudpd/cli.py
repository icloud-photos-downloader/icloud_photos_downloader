import argparse
import copy
import sys
from dataclasses import dataclass
from typing import List, Sequence, Tuple


def add_options_for_user(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    cloned = copy.deepcopy(parser)
    cloned.add_argument("-d", "--directory")
    return cloned


def add_user_option(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    cloned = copy.deepcopy(parser)
    cloned.add_argument("-u", "--username")
    return cloned


def add_global_options(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    cloned = copy.deepcopy(parser)
    cloned.add_argument("--use-os-locale", action="store_true")
    group = cloned.add_mutually_exclusive_group()
    group.add_argument("--help", "-h", "-?", action="store_true")
    group.add_argument("--version", action="store_true")
    return cloned


def split(splitter: Sequence[str], inp: Sequence[str]) -> Sequence[Sequence[str]]:
    result: List[List[str]] = [[]]
    for item in inp:
        if item in splitter:
            #  add group
            result.append([])
        else:
            pass
        group_index = len(result) - 1
        result[group_index].append(item)
    return result


def format_help() -> str:
    # create fake parser and return it's help
    global_help = add_global_options(
        argparse.ArgumentParser(exit_on_error=False, add_help=False)
    ).format_help()
    default_help = add_options_for_user(
        argparse.ArgumentParser(exit_on_error=False, add_help=False)
    ).format_help()
    user_help = add_options_for_user(
        add_user_option(argparse.ArgumentParser(exit_on_error=False, add_help=False))
    ).format_help()
    return "\n".join([global_help, default_help, user_help])


@dataclass
class _DefaultConfig:
    directory: str


@dataclass
class Config(_DefaultConfig):
    username: str


@dataclass
class GlobalConfig:
    help: bool
    version: bool
    use_os_locale: bool


def parse(args: Sequence[str]) -> Tuple[GlobalConfig, Sequence[Config]]:
    # default --help
    if len(args) == 0:
        args = ["--help"]
    else:
        pass

    splitted_args = split(["-u", "--username"], args)
    global_and_default_args = splitted_args[0]
    global_parser: argparse.ArgumentParser = add_global_options(
        argparse.ArgumentParser(exit_on_error=False, add_help=False)
    )
    global_ns, rest_args = global_parser.parse_known_args(global_and_default_args)

    default_parser: argparse.ArgumentParser = add_options_for_user(
        argparse.ArgumentParser(exit_on_error=False, add_help=False)
    )

    default_ns = default_parser.parse_args(rest_args)

    user_parser: argparse.ArgumentParser = add_user_option(
        add_options_for_user(argparse.ArgumentParser(exit_on_error=False, add_help=False))
    )
    user_nses = [
        Config(**vars(user_parser.parse_args(user_args, copy.deepcopy(default_ns))))
        for user_args in splitted_args[1:]
    ]

    return (GlobalConfig(**vars(global_ns)), user_nses)


def cli() -> int:
    global_ns, user_nses = parse(sys.argv[1:])
    if global_ns.help:
        print(format_help())
        return 0
    elif global_ns.version:
        print("version printed here")
        return 0
    else:
        print(f"global_ns={global_ns}")
        for user_ns in user_nses:
            print(f"user_ns={user_ns}")
    return 0
