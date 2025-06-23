#!/usr/bin/env python3
"""takes results of compatibility tests and compie into one file"""

import os
import sys

from compile_matrix import print_breakdowns


def content_checker(filepath):
    return os.path.getsize(filepath) > 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Params: <version-thumbprint-file> [folder]")
        sys.exit(1)
    print("## Minimal Effort Compatibility")
    print(
        "Checks if `icloudpd` can be installed using minimal effort and ran bare minimum functionality of displaying a version information. Minimal effort may require installing default version of package manager using OS tools"
    )
    print("")
    version_thumbprint_file = sys.argv[1]
    with open(version_thumbprint_file) as file:
        version_thumbprint = file.read()
        print(f"Version: {version_thumbprint}")
        print("")
    folder = sys.argv[2] if len(sys.argv) > 2 else "."
    print_breakdowns(folder, content_checker, ("(src)", "Test pass using src (for pip)"))
