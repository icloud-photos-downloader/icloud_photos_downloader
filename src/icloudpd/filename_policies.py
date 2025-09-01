"""Filename building utilities with policy application"""

from typing import Callable

from foundation.core import partial_2_1
from pyicloud_ipd.file_match import FileMatchPolicy
from pyicloud_ipd.services.photos import (
    PhotoAsset,
    apply_file_match_policy,
    apply_filename_cleaner,
    filename_with_fallback,
)


def build_filename_with_policies(
    file_match_policy: FileMatchPolicy,
    filename_cleaner: Callable[[str], str],
    photo: PhotoAsset,
) -> str:
    """Build filename applying cleaner and file match policy transformations."""
    extract_with_fallback = filename_with_fallback(photo.id, photo.item_type_extension)
    raw_filename = extract_with_fallback(photo.calculate_filename())
    filename_cleaner_transformer = apply_filename_cleaner(filename_cleaner)
    cleaned_filename = filename_cleaner_transformer(raw_filename)
    policy_transformer = apply_file_match_policy(file_match_policy, photo.id)
    return policy_transformer(cleaned_filename)


def create_filename_builder(
    file_match_policy: FileMatchPolicy,
    filename_cleaner: Callable[[str], str],
) -> Callable[[PhotoAsset], str]:
    """Create a filename builder function with pre-configured policy and cleaner.

    This factory function uses partial_2_1 for better type safety compared to functools.partial.
    The resulting function only needs a PhotoAsset to produce the final filename.

    Args:
        file_match_policy: Policy for transforming filenames (e.g., NAME_ID_DEDUPE_SUFFIX)
        filename_cleaner: Function to clean/transform raw filenames (unicode handling)

    Returns:
        A function that takes only a PhotoAsset and returns the processed filename

    Example:
        # Set up once per config
        filename_builder = create_filename_builder(policy, cleaner)

        # Use many times per photo
        for photo in photos:
            filename = filename_builder(photo)
    """
    return partial_2_1(build_filename_with_policies, file_match_policy, filename_cleaner)
