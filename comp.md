# Minimal Effort Compatibility
Checks if icloudpd can be installed using minimal effort. Minimal effort may require installing default version of package manager using OS tools

Legend:
- N/A - not applicable/available
- pass - test pass
- fail - test fail
- pass (src) - test pass using src (for pip)
## bin
OSes and distros|386|amd64|arm32v5|arm32v6|arm32v7|arm64
-|-|-|-|-|-|-
alpine_3_10|pass|pass|N/A|fail|pass|pass
alpine_3_11|pass|pass|N/A|fail|pass|pass
alpine_3_12|pass|pass|N/A|fail|pass|pass
alpine_3_13|pass|pass|N/A|fail|pass|pass
alpine_3_14|pass|pass|N/A|fail|pass|pass
alpine_3_15|pass|pass|N/A|fail|pass|pass
alpine_3_16|pass|pass|N/A|fail|pass|pass
alpine_3_17|pass|pass|N/A|fail|pass|pass
alpine_3_18|pass|pass|N/A|fail|pass|pass
alpine_3_19|pass|pass|N/A|fail|pass|pass
debian_10_buster|pass|pass|fail|N/A|pass|pass
debian_11_bullseye|pass|pass|fail|N/A|pass|pass
debian_12_bookworm|pass|pass|fail|N/A|pass|pass
debian_6_squeeze|N/A|pass|N/A|N/A|N/A|fail
debian_7_wheezy|pass|pass|fail|N/A|pass|pass
debian_8_jessie|pass|pass|fail|N/A|pass|pass
debian_9_stretch|pass|pass|fail|N/A|pass|pass
macos-11|N/A|pass|N/A|N/A|N/A|N/A
macos-12|N/A|pass|N/A|N/A|N/A|N/A
ubuntu_12_precise|fail|pass|N/A|N/A|N/A|fail
ubuntu_14_trusty|pass|pass|N/A|N/A|pass|pass
ubuntu_16_xenial|pass|pass|N/A|N/A|pass|pass
ubuntu_18_bionic|pass|pass|N/A|N/A|pass|pass
ubuntu_20_focal|pass|pass|N/A|N/A|pass|pass
ubuntu_22_jammy|N/A|pass|N/A|N/A|pass|pass
windows-2019|N/A|pass|N/A|N/A|N/A|N/A
windows-2022|N/A|pass|N/A|N/A|N/A|N/A
## docker
OSes and distros|amd64
-|-
linux|pass
## pip
OSes and distros|386|amd64|arm32v5|arm32v6|arm32v7|arm64
-|-|-|-|-|-|-
alpine_3_10|fail|fail|N/A|fail|fail|fail
alpine_3_11|fail|fail|N/A|fail|fail|fail
alpine_3_12|fail|fail|N/A|fail|fail|fail
alpine_3_13|pass|pass|N/A|pass|pass|pass
alpine_3_14|pass|pass|N/A|pass|pass|pass
alpine_3_15|pass|pass|N/A|pass|pass|pass
alpine_3_16|pass|pass|N/A|pass|pass|pass
alpine_3_17|pass|pass|N/A|pass|pass|pass
alpine_3_18|pass|pass|N/A|pass|pass|pass
alpine_3_19|pass|pass|N/A|pass|pass|pass
debian_10_buster|pass|pass|fail|N/A|fail|fail
debian_11_bullseye|pass|pass|fail|N/A|pass|pass
debian_12_bookworm|pass|pass|fail|N/A|pass|pass
macos-11|N/A|pass|N/A|N/A|N/A|N/A
macos-12|N/A|pass|N/A|N/A|N/A|N/A
python3_12|pass|pass|fail|N/A|pass|pass
python3_12_alpine3_18|pass|pass|N/A|pass|pass|pass
ubuntu_16_xenial|pass|pass|N/A|N/A|fail|fail
ubuntu_18_bionic|pass|pass|N/A|N/A|fail|fail
ubuntu_20_focal|pass|pass|N/A|N/A|pass|pass
ubuntu_22_jammy|N/A|pass|N/A|N/A|pass|pass
windows-2019|N/A|pass|N/A|N/A|N/A|N/A
windows-2022|N/A|pass|N/A|N/A|N/A|N/A