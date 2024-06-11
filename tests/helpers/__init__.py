import glob
import os
import shutil
import traceback
from typing import Any, Callable, Iterable, List, Protocol, Sequence, Tuple, TypeVar
from click.testing import Result
from icloudpd.base import main
from click.testing import CliRunner
import vcr

def print_result_exception(result: Result) -> None:
    ex = result.exception
    if ex:
        # This only works on Python 3
        if hasattr(ex, '__traceback__'):
            traceback.print_exception(type(ex),
                value=ex, tb=ex.__traceback__)
        else:
            print(ex)

def path_from_project_root(file_name:str) -> str:
    parent = os.path.relpath(os.path.dirname(file_name), "./")
    return parent

def recreate_path(path_name: str) -> None:
    """Removes if exists and creates dir"""
    if os.path.exists(path_name):
        shutil.rmtree(path_name)
    os.makedirs(path_name)

def create_files(data_dir:str, files_to_create: Sequence[Tuple[str, str, int]]) -> None:
    for (dir_name, file_name, file_size) in files_to_create:
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


def combine_file_lists(files_to_create: Sequence[Tuple[str, str, int]], files_to_download: List[Tuple[str, str]]) -> Sequence[Tuple[str, str]]:
    return ([(dir_name, file_name) for (dir_name, file_name, _) in files_to_create]) + files_to_download

_T = TypeVar("_T")

class AssertEquality(Protocol):
    def __call__(self, __first: _T, __second: _T, __msg: str) -> None: ...

def assert_files(assert_equal: AssertEquality, data_dir: str, files_to_assert: Sequence[Tuple[str, str]]) -> None:
        files_in_result = glob.glob(os.path.join(
            data_dir, "**/*.*"), recursive=True)

        assert_equal(sum(1 for _ in files_in_result), len(files_to_assert), "File count does not match")

        for dir_name, file_name in files_to_assert:
            normalized_dir_name = os.path.normpath(dir_name)
            file_path = os.path.join(normalized_dir_name, file_name)
            assert_equal(os.path.exists(os.path.join(data_dir, file_path)), True, f"File {file_path} expected, but does not exist")

def run_cassette(cassette_path: str, params: Sequence[str]) -> Result:
    with vcr.use_cassette(cassette_path):
        # Pass fixed client ID via environment variable
        runner = CliRunner(env={
            "CLIENT_ID": "DE309E26-942E-11E8-92F5-14109FE0B321"
        })
        result = runner.invoke(
            main,
            params,
        )
        print_result_exception(result)
        return result

def run_icloudpd_test(
        assert_equal: AssertEquality, 
        vcr_path:str, 
        base_dir: str, 
        cassette_filename: str, 
        files_to_create: Sequence[Tuple[str, str, int]], 
        files_to_download: List[Tuple[str, str]], 
        params: List[str]) -> Tuple[str, Result]:
    cookie_dir = os.path.join(base_dir, "cookie")
    data_dir = os.path.join(base_dir, "data")

    for dir in [base_dir, cookie_dir, data_dir]:
        recreate_path(dir)

    create_files(data_dir, files_to_create)

    result = run_cassette(os.path.join(vcr_path, cassette_filename),
            [
                "-d",
                data_dir,
                "--cookie-directory",
                cookie_dir,
            ] + params,
        )

    files_to_assert = combine_file_lists(files_to_create, files_to_download)
    assert_files(assert_equal, data_dir, files_to_assert)
    
    return (data_dir, result)
