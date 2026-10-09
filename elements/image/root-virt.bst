# SPDX-License-Identifier: MIT

kind: script
description: |
  Finalised Virt root: integration toolbox removed, root-identity policy applied, system
  users created, presets applied, an uninitialized machine-id and an empty /var. Tools run
  from the build sandbox; the OS tree is only data at /sysroot.

build-depends:
- junctions/freedesktop-sdk.bst:public-stacks/runtime-gnu.bst
- junctions/freedesktop-sdk.bst:components/findutils.bst
- junctions/freedesktop-sdk.bst:components/systemd.bst
- filename: image/root-virt-tree.bst
  config:
    location: /sysroot
# Reference trees used to compute exactly which files the toolbox added.
- filename: image/integration-tools.bst
  config:
    location: /reference/tools
- filename: profiles/virt.bst
  config:
    location: /reference/os
# System users of the official extensions, created here because /etc is read-only.
- filename: extensions/desktop-gnome-sysusers.bst
  config:
    location: /extension-sysusers
# The public update keyring systemd-pull verifies channel signatures against.
- security/keys-update.bst

config:
  commands:
  - |
    mkdir -p /work
    (cd /reference/tools && find . -mindepth 1 ! -type d | sort) > /work/tools-files
    (cd /reference/os && find . -mindepth 1 ! -type d | sort) > /work/os-files
    (cd /reference/tools && find . -mindepth 1 -type d | sort) > /work/tools-dirs
    (cd /reference/os && find . -mindepth 1 -type d | sort) > /work/os-dirs
    comm -23 /work/tools-files /work/os-files > /work/remove-files
    comm -23 /work/tools-dirs /work/os-dirs | sort -r > /work/remove-dirs
    while IFS= read -r path; do rm -f "/sysroot/${path#./}"; done < /work/remove-files
    while IFS= read -r path; do rmdir "/sysroot/${path#./}" 2>/dev/null || true; done < /work/remove-dirs
    echo "Removed $(wc -l < /work/remove-files) integration toolbox files"

  - |
    # docs/spec.md §18.1: su is absent. util-linux ships it and systemd depends on
    # util-linux, so it is removed here rather than by forking FDSDK's recipe.
    rm -f /sysroot/usr/bin/su /sysroot/etc/pam.d/su /sysroot/etc/pam.d/su-l
    # pkexec (polkit's setuid command runner) is absent too: run0 is the only escalation
    # (docs/spec.md §19, docs/decisions.md D55).
    rm -f /sysroot/usr/bin/pkexec
    # Updates verify against Beamline's keyring only (docs/decisions.md D52). systemd-pull
    # reads its vendor keyring, plus /etc/systemd/import-pubring.pgp when present; the vendor
    # keyring systemd ships (other distributions' keys) is replaced.
    install -Dm644 "%{datadir}/%{os-id}/keys/update/import-pubring.pgp" \
      /sysroot%{indep-libdir}/systemd/import-pubring.pgp

  - |
    # /etc is read-only on the running system (docs/spec.md §14, docs/decisions.md D27), so
    # system users are created now: the base's and those of the official extensions
    # (§18.2, D38). The extensions' sysusers.d files ship with the extensions, so they are
    # only borrowed here. sysusers writes mode 0000; the unprivileged build sandbox must
    # still read the files to copy them.
    borrowed="$(cd /extension-sysusers%{datadir}/%{os-id}/extension-sysusers && find . -name '*.conf' | sort)"
    for conf in ${borrowed}; do
      install -m644 "/extension-sysusers%{datadir}/%{os-id}/extension-sysusers/${conf}" \
        "/sysroot/usr/lib/sysusers.d/beamline-extension-$(basename "${conf}")"
    done
    systemd-sysusers --root=/sysroot
    rm -f /sysroot/usr/lib/sysusers.d/beamline-extension-*.conf
    chmod 0400 /sysroot/etc/shadow /sysroot/etc/gshadow
    # Root is locked with a nologin shell (docs/spec.md §18.1, docs/decisions.md D55).
    while IFS=: read -r name _ uid _ _ _ shell; do
      [ "${name}" = root ] || continue
      [ "${uid}" = 0 ] && [ "${shell}" = /usr/bin/nologin ] || { echo "root: uid ${uid}, shell ${shell}" >&2; exit 1; }
    done < /sysroot/etc/passwd
    while IFS=: read -r name password _; do
      [ "${name}" = root ] || continue
      case "${password}" in '!'*) ;; *) echo "root is not locked" >&2; exit 1 ;; esac
    done < /sysroot/etc/shadow

  - systemctl --root=/sysroot preset-all

  - |
    # "uninitialized" marks a first boot: PID 1 overmounts a transient ID, and
    # systemd-machine-id-commit saves it in /etc's mutable layer, which the initrd merges on
    # later boots, so they are not first boots (docs/decisions.md D56).
    rm -f /sysroot/etc/machine-id
    printf 'uninitialized\n' > /sysroot/etc/machine-id
    chmod 0444 /sysroot/etc/machine-id
    # /etc is up to date with /usr by construction. Once the mutable layer makes /etc
    # writable, a missing /etc/.updated would start ldconfig, sysusers and hwdb-update
    # (ConditionNeedsUpdate=/etc), which would write into it (docs/decisions.md D56). Every
    # staged file carries the same timestamp, so the condition stays false.
    printf 'TIMESTAMP_NSEC=%s000000000\n' "%{source-date-epoch}" > /sysroot/etc/.updated

  - |
    # /var is state: tmpfiles and the services populate it at boot (§14). /data is the
    # mount point of DATA; /var and /home are bind mounts from it (§15).
    find /sysroot/var -mindepth 1 -delete
    mkdir -p /sysroot/data
    # Mount points for the boot partitions: systemd's gpt-auto generator mounts the ESP at
    # /efi and XBOOTLDR at /boot (docs/spec.md §15).
    mkdir -p /sysroot/efi /sysroot/boot

  - |
    # The root is read-only at runtime, so what boot-time services would write into it
    # is created now: the dynamic linker cache (ldconfig.service runs whenever it is
    # missing), and what tmpfiles creates outside the state and API filesystems
    # (/etc/mtab, factory copies into /etc, ...). ldconfig -r refuses the relative
    # "include ld.so.conf.d/*.conf" of /etc/ld.so.conf, so it reads the same snippets
    # through a temporary configuration with an absolute include.
    echo 'include /etc/ld.so.conf.d/*.conf' > /sysroot/etc/ld.so.conf.image-build
    ldconfig -X -r /sysroot -f /etc/ld.so.conf.image-build
    rm /sysroot/etc/ld.so.conf.image-build
    systemd-tmpfiles --root=/sysroot --create --boot \
      --exclude-prefix=/dev --exclude-prefix=/proc --exclude-prefix=/sys \
      --exclude-prefix=/run --exclude-prefix=/tmp --exclude-prefix=/var \
      --exclude-prefix=/home --exclude-prefix=/data

  - cp -a /sysroot/. "%{install-root}/"
