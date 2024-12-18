#!/usr/bin/env python3
"""takes results of tz and locale compatibility tests and compile into one file"""

import sys

from compile_matrix import print_breakdowns


def special_content_checker(expected_content):
    # content is special when it exists, but is invalid
    def _intern(filepath):
        with open(filepath, encoding="UTF-8") as file:
            content = file.read().strip()
            return content not in expected_content

    return _intern


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Params: <folder> <expected content> [<expected content>...]")
        sys.exit(1)
    print("## Timezone and Locale Compatibility")
    print(
        "Checks if `icloudpd` can be installed using minimal effort and ran bare minimum functionality of displaying version and commit timestamp in local timezone and RU locale. Minimal effort may require installing default version of package manager, timezone data, and locales using OS tools"
    )
    print("")
    folder = sys.argv[1]
    expected_content = [c.strip() for c in sys.argv[2:]]
    # content is special when it exists, but is invalid
    print_breakdowns(
        folder,
        special_content_checker(expected_content),
        ("(invalid)", "Incorrect values were generated"),
    )
