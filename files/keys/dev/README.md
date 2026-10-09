# Development keys: DEVELOPMENT ONLY, NOT TRUSTED

These keys are committed to the repository on purpose (docs/security.md §5.4, §19.4). Anyone
can read them, so nothing signed with them is authentic. They exist so that every build,
anywhere, signs the same way and stays reproducible. Only development boot configurations
trust them. Production keys never enter the repository or a build worker.

| Directory | Scope | Used by |
|---|---|---|
| `uki/` | Secure Boot db key: signs UKIs and systemd-boot | `image/uki-virt.bst` |
| `verity/` | Signs extension images' verity root hashes | extension images (`include/extension.yml`) |
| `update/` | OpenPGP key: signs the SHA256SUMS of snapshot and channel directories | `tools/integrate.py` |
| `kernel-modules/` | Module signing key; the kernel enforces signatures (`MODULE_SIG_FORCE`) | `kernel/linux-virt.bst` |

One key per scope: a key for one scope never authorises another (security §5.4). Until
production keys exist, the production UKI is signed with the development key too; the
command line, not the key, distinguishes it from the development UKI (security §19.4).

Generated once by `tools/make-dev-keys`.
