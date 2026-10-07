# SPDX-License-Identifier: MIT

kind: manual
description: |
  Project-owned Linux for the Virt profile (docs/spec.md §11.4): virtio boot path
  built in, LLVM toolchain, release channel.

(@):
- include/kernel/release.yml
- include/kernel/build.yml

variables:
  kernel-profile: virt
