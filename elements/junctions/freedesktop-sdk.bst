# SPDX-License-Identifier: MIT
#
# Freedesktop SDK is the substrate (docs/spec.md §2.2): toolchain, libraries and
# component recipes. It does not define distribution policy.
#
# Tracked at `master` (§31): integration cycles select the newest master commit whose
# upstream CI pipeline passed, so FDSDK's published artifacts exist for it.
#
# Keep options at FDSDK defaults (apart from arch) so cache keys match the artifacts
# FDSDK publishes to cache.freedesktop-sdk.io; anything else forces local rebuilds.

kind: junction

sources:
- kind: git_repo
  url: gitlab:freedesktop-sdk/freedesktop-sdk.git
  track: master

config:
  options:
    target_arch: '%{arch}'
    bootstrap_build_arch: '%{arch}'

  # Components tracked at their own upstream HEAD (docs/spec.md §2.2, decisions D15).
  overrides:
    components/_private/systemd-base.bst: overrides/systemd-base.bst
    components/systemd.bst: overrides/systemd.bst
