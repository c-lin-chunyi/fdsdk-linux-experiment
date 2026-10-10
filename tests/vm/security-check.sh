# SPDX-License-Identifier: MIT
#
# Negative security tests (ci/test-security; docs/security.md §15; docs/decisions.md D59), on an
# enforcing production boot. beamline-security-check.service runs this as root in init_t, the
# test harness; every check runs in the context it tests, through a transient unit
# (systemd-run --pipe, with SELinuxContext= and User=). Checks that must be refused run as root,
# so that SELinux, not file permissions, is what refuses them. Each refusal they provoke is listed
# in policy/selinux-expected.toml. Never part of an image.

set -u
P0=user_u:user_r:user_t:s0
ADMIN=admin_u:admin_r:admin_t:s0
UPDATER=system_u:system_r:sysupdate_t:s0
failed=0

result() {
    if [ "$2" = ok ]; then echo "SECURITY $1: ok"; else echo "SECURITY $1: FAILED ($3)"; failed=1; fi
}

# run CONTEXT USER COMMAND: the command's output, then its exit status as "status=N".
run() {
    systemd-run --quiet --wait --pipe --collect --property="SELinuxContext=$1" \
        --property="User=$2" /usr/bin/sh -c "$3" 2>&1
    echo "status=$?"
}

read -r enforce < /sys/fs/selinux/enforce
[ "$enforce" = 1 ] && result enforcing ok || result enforcing failed "SELinux is not enforcing"

# The admin extension provides cp, insmod and setenforce.
systemctl start beamline-admin.service

# P0 executes an arbitrary, unsigned ELF it placed in a writable directory: allowed.
out=$(run "$P0" alice 'cp /usr/bin/dash /var/tmp/p0-elf && /var/tmp/p0-elf -c "echo P0_ELF_RAN"')
case "$out" in *P0_ELF_RAN*) result p0-runs-own-elf ok ;; *) result p0-runs-own-elf failed "$out" ;; esac

# P0 modifies verified /usr: refused (read-only, verity-backed SYSTEM).
out=$(run "$P0" root ': > /usr/lib/beamline-p0 && echo WROTE_USR')
case "$out" in *WROTE_USR*) result p0-writes-usr failed "$out" ;; *) result p0-writes-usr ok ;; esac

# P0 and admin write a file outside /etc's allowlist: refused by SELinux, even as root.
for who in p0:"$P0" admin:"$ADMIN"; do
    out=$(run "${who#*:}" root 'printf "# beamline\n" >> /etc/pam.d/login && echo WROTE_ETC')
    case "$out" in *WROTE_ETC*) result "${who%%:*}-writes-etc" failed "$out" ;; *) result "${who%%:*}-writes-etc" ok ;; esac
done

# admin changes an allowlisted setting in place: allowed.
out=$(run "$ADMIN" root 'printf "beamline-security\n" > /etc/hostname && echo WROTE_HOSTNAME')
case "$out" in *WROTE_HOSTNAME*) result admin-writes-setting ok ;; *) result admin-writes-setting failed "$out" ;; esac

# P0 enters the updater's or the admin domain through /proc/self/attr/exec: refused.
for target in sysupdate:"$UPDATER" admin:"$ADMIN"; do
    out=$(run "$P0" root "printf %s '${target#*:}' > /proc/self/attr/exec && exec /usr/bin/sh -c 'echo ENTERED'")
    case "$out" in *ENTERED*) result "p0-enters-${target%%:*}" failed "$out" ;; *) result "p0-enters-${target%%:*}" ok ;; esac
done

# The P3 updater executes a helper from /var/tmp: refused.
out=$(run "$UPDATER" root '/var/tmp/p0-elf -c "echo HELPER_RAN"')
case "$out" in *HELPER_RAN*) result updater-runs-tmp-helper failed "$out" ;; *) result updater-runs-tmp-helper ok ;; esac

# admin switches SELinux to permissive: refused, and enforcement stays on.
out=$(run "$ADMIN" root 'setenforce 0 && echo SETENFORCE_DONE')
read -r enforce < /sys/fs/selinux/enforce
case "$out:$enforce" in *SETENFORCE_DONE*|*:0) result admin-setenforce failed "$out" ;; *) result admin-setenforce ok ;; esac

# admin loads a kernel module (any file; it is not signed): refused.
out=$(run "$ADMIN" root 'insmod /var/tmp/p0-elf && echo MODULE_LOADED')
case "$out" in *MODULE_LOADED*) result admin-loads-module failed "$out" ;; *) result admin-loads-module ok ;; esac

# alice reads dev's home while dev's home is active: refused.
PASSWORD=dev homectl activate dev
out=$(run "$P0" alice 'cd /home/dev && echo READ_DEV_HOME')
homectl deactivate dev
case "$out" in *READ_DEV_HOME*) result p0-reads-other-home failed "$out" ;; *) result p0-reads-other-home ok ;; esac

rm -f /var/tmp/p0-elf
[ "$failed" = 0 ] && echo BEAMLINE_SECURITY_OK || echo BEAMLINE_SECURITY_FAILED
