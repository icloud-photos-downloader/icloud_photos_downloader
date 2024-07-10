#!/usr/bin/env python3
"""takes results of compatibility tests and compie into one file"""

from compile_matrix import print_breakdowns

if __name__ == "__main__":
    print("## Minimal Effort Compatibility")
    print(
        "Checks if `icloudpd` can be installed using minimal effort and ran bare minimum functionality of displaying a version information. Minimal effort may require installing default version of package manager using OS tools"
    )
    print("")
    print_breakdowns()
