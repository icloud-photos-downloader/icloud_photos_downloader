#!/usr/bin/env python3
"""takes results of tz and locale compatibility tests and compile into one file"""

from compile_matrix import print_breakdowns

if __name__ == "__main__":
    print("## Timezone and Locale Compatibility")
    print(
        "Checks if `icloudpd` can be installed using minimal effort and ran bare minimum functionality of displaying version and commit timestamp in local timezone and RU locale. Minimal effort may require installing default version of package manager, timezone data, and locales using OS tools"
    )
    print("")
    print_breakdowns()
