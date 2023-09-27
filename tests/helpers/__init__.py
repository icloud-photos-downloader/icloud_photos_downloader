import os
import shutil
import traceback
from click.testing import Result


def print_result_exception(result: Result):
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
