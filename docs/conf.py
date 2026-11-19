# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import tomllib
from pathlib import Path

with open(Path(__file__).resolve().parent.parent / "pyproject.toml", "rb") as f:
    _version = tomllib.load(f)["project"]["version"]

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "icloudpd"
copyright = "2024-2026, Contributors"
author = "Contributors"
release = _version

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = ["myst_parser"]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_title = f"icloudpd {release}"
language = "en"

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "furo"
# html_static_path = ['_static']

# myst config
myst_enable_extensions = ["deflist"]
