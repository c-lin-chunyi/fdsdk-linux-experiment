# SPDX-License-Identifier: MIT
#
# Freedesktop SDK is the substrate (docs/spec.md §2.2): toolchain, libraries and
# component recipes. It does not define distribution policy.
#
# Keep options at FDSDK defaults (apart from arch) so cache keys match the artifacts
# FDSDK publishes to cache.freedesktop-sdk.io; anything else forces local rebuilds.

kind: junction

sources:
- kind: git_repo
  url: gitlab:freedesktop-sdk/freedesktop-sdk.git
  track: freedesktop-sdk-26.08*

config:
  options:
    target_arch: '%{arch}'
    bootstrap_build_arch: '%{arch}'
