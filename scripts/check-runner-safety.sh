#!/usr/bin/env bash
set -euo pipefail

failures=()
if (( EUID == 0 )); then
    failures+=("runner executes as root")
fi

for device in /dev/dri /dev/input /dev/kvm /dev/mem; do
    if [[ -e "$device" && ( -r "$device" || -w "$device" ) ]]; then
        failures+=("runner can access $device")
    fi
done
for socket in /var/run/docker.sock /run/docker.sock; do
    if [[ -S "$socket" && ( -r "$socket" || -w "$socket" ) ]]; then
        failures+=("runner can access privileged socket $socket")
    fi
done

if ((${#failures[@]})); then
    printf 'Runner safety check failed:\n' >&2
    printf '  - %s\n' "${failures[@]}" >&2
    exit 1
fi

umask_value="$(umask)"
if [[ "$umask_value" != "0022" && "$umask_value" != "0077" && "$umask_value" != "022" && "$umask_value" != "077" ]]; then
    echo "Runner safety check failed: unexpected umask $umask_value" >&2
    exit 1
fi

echo "Runner safety passed (unprivileged, no DRM/input/KVM/Docker socket exposure)"
