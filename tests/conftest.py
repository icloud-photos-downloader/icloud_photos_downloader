import os
import time

import tzlocal

# Expected folders and dates in the tests are written for UTC, so run them in UTC whatever the
# machine's time zone is. tzlocal reads TZ on all platforms; tzset makes the C library follow too.
os.environ["TZ"] = "Etc/UTC"
if hasattr(time, "tzset"):
    time.tzset()
tzlocal.reload_localzone()
