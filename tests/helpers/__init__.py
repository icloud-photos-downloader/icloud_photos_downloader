import glob
import os
import shutil
import traceback
from functools import partial
from typing import IO, Any, Callable, List, Mapping, Protocol, Sequence, Tuple, TypeVar

from click.testing import CliRunner, Result
from vcr import VCR

from foundation.core import compose, flip, partial_1_1, partial_2_1
from icloudpd.base import main

vcr = VCR(decode_compressed_response=True, record_mode="none")


def print_result_exception(result: Result) -> Result:
    ex = result.exception
    if ex:
        # This only works on Python 3
        if hasattr(ex, "__traceback__"):
            traceback.print_exception(type(ex), value=ex, tb=ex.__traceback__)
        else:
            print(ex)
    return result


def path_from_project_root(file_name: str) -> str:
    parent = os.path.relpath(os.path.dirname(file_name), "./")
    return parent


def recreate_path(path_name: str) -> None:
    """Removes if exists and creates dir"""
    if os.path.exists(path_name):
        shutil.rmtree(path_name)
    os.makedirs(path_name)


def create_files(data_dir: str, files_to_create: Sequence[Tuple[str, str, int]]) -> None:
    for dir_name, file_name, file_size in files_to_create:
        normalized_dir_name = os.path.normpath(dir_name)
        os.makedirs(os.path.join(data_dir, normalized_dir_name), exist_ok=True)
        with open(os.path.join(data_dir, normalized_dir_name, file_name), "a") as f:
            f.truncate(file_size)


# TypeVar to parameterize for specific types
# _SA = TypeVar('_SA', bound='SupportsAdd')

# class SupportsAdd(Protocol):
#     """Any type T where +(:T, :T) -> T"""
#     def __add__(self: _SA, other: _SA) -> _SA: ...

# class IterableAdd(SupportsAdd, Iterable, Protocol): ...


def combine_file_lists(
    files_to_create: Sequence[Tuple[str, str, int]], files_to_download: List[Tuple[str, str]]
) -> Sequence[Tuple[str, str]]:
    return (
        [(dir_name, file_name) for (dir_name, file_name, _) in files_to_create]
    ) + files_to_download


_T = TypeVar("_T")
_T_co = TypeVar("_T_co", covariant=True)
_T_contra = TypeVar("_T_contra", contravariant=True)


class AssertEquality(Protocol):
    def __call__(self, __first: _T, __second: _T, __msg: str) -> None: ...


def assert_files(
    assert_equal: AssertEquality, data_dir: str, files_to_assert: Sequence[Tuple[str, str]]
) -> None:
    files_in_result = glob.glob(os.path.join(data_dir, "**/*.*"), recursive=True)

    assert_equal(sum(1 for _ in files_in_result), len(files_to_assert), "File count does not match")

    for dir_name, file_name in files_to_assert:
        normalized_dir_name = os.path.normpath(dir_name)
        file_path = os.path.join(normalized_dir_name, file_name)
        assert_equal(
            os.path.exists(os.path.join(data_dir, file_path)),
            True,
            f"File {file_path} expected, but does not exist",
        )


DEFAULT_ENV: Mapping[str, str | None] = {"CLIENT_ID": "DE309E26-942E-11E8-92F5-14109FE0B321"}


def run_main_env(
    env: Mapping[str, str | None], params: Sequence[str], input: str | bytes | IO[Any] | None = None
) -> Result:
    runner = CliRunner(env=env)
    result = runner.invoke(main, params, input)
    return result


run_main: Callable[[Sequence[str]], Result] = compose(
    print_result_exception, partial_1_1(run_main_env, DEFAULT_ENV)
)


def run_with_cassette(cassette_path: str, f: Callable[[_T_contra], _T_co], inp: _T_contra) -> _T_co:
    with vcr.use_cassette(cassette_path):
        return f(inp)


def run_cassette(
    cassette_path: str, params: Sequence[str], input: str | bytes | IO[Any] | None = None
) -> Result:
    with vcr.use_cassette(cassette_path):
        return print_result_exception(run_main_env(DEFAULT_ENV, params, input))


_path_join_flipped = flip(os.path.join)

calc_data_dir = partial_1_1(_path_join_flipped, "data")
calc_cookie_dir = partial_1_1(_path_join_flipped, "cookie")
calc_vcr_dir = partial_1_1(_path_join_flipped, "vcr_cassettes")


def run_icloudpd_test(
    assert_equal: AssertEquality,
    root_path: str,
    base_dir: str,
    cassette_filename: str,
    files_to_create: Sequence[Tuple[str, str, int]],
    files_to_download: List[Tuple[str, str]],
    params: List[str],
    additional_env: Mapping[str, str | None] = {},
    input: str | bytes | IO[Any] | None = None,
) -> Tuple[str, Result]:
    cookie_dir = calc_cookie_dir(base_dir)
    data_dir = calc_data_dir(base_dir)
    vcr_path = calc_vcr_dir(root_path)
    cookie_master_path = calc_cookie_dir(root_path)

    for dir in [base_dir, data_dir]:
        recreate_path(dir)

    shutil.copytree(cookie_master_path, cookie_dir)

    create_files(data_dir, files_to_create)

    combined_env: Mapping[str, str | None] = {**additional_env, **DEFAULT_ENV}

    main_runner = compose(print_result_exception, partial(run_main_env, combined_env, input=input))

    with_cassette_main_runner = partial_2_1(
        run_with_cassette, os.path.join(vcr_path, cassette_filename), main_runner
    )

    combined_params = [
        "-d",
        data_dir,
        "--cookie-directory",
        cookie_dir,
    ] + params

    result = with_cassette_main_runner(combined_params)
    files_to_assert = combine_file_lists(files_to_create, files_to_download)
    assert_files(assert_equal, data_dir, files_to_assert)

    return (data_dir, result)
