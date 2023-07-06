import os, sys, subprocess
sys.exit(subprocess.call([
    os.path.join(os.path.dirname(__file__), "icloudpd"),
    *sys.argv[1:]
]))