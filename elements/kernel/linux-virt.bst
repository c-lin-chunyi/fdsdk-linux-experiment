# SPDX-License-Identifier: MIT

kind: manual
description: |
  Project-owned Linux for the Virt profile (docs/spec.md §11.4): narrow (allnoconfig plus
  fragments), virtio boot path built in, module support kept, LLVM toolchain, Linux
  master resolved by the integration cycle.

(@):
- include/kernel/linux.yml
- include/kernel/build.yml

variables:
  kernel-profile: virt
  kernel-base: allnoconfig
