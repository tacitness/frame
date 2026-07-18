# Manual hardware acceptance

These checks are intentionally excluded from hooks and CI. Run only from a recoverable local TTY with a human present, after
reading the corresponding README mode instructions and ensuring another login/reboot path exists.

Record: commit/tag, host, CPU, GPU/driver, kernel, command, device permissions, display-manager state, expected result, actual logs,
cleanup/recovery, and post-test health.

## Matrix

| Area | Cases | Required recovery evidence |
|---|---|---|
| DRM read-only probe | no card, permission denied, disconnected/connected outputs, multiple cards | No master/state change; descriptors close |
| Modeset | acquire failure, preferred mode, signal during each acquisition stage, normal restore | Original CRTC restored; FB/map/handle/master/fd released |
| Display compositor | single/dual output, page flip, VT away/back, blank/unblank | No wedged master or stale scanout; full repaint on return |
| Hotplug/device loss | connect/disconnect, error/hangup, in-flight flip | No busy loop; state rebuilt or degraded safely |
| evdev | enumerate, permission denied, partial/batched record, unplug | No grabbed/stale device; fd removed from polling |
| Synthetic input parity | key/button/motion/layout through FIFO | Same routing/state as evdev without opening live devices |

Do not use `sudo` merely to make a failure disappear. Record the intended user/group/device policy and test it explicitly.
