---
description: 'Headless deterministic test and benchmark standards'
applyTo: 'tests/**,scripts/benchmark-*.py'
---

# Test instructions

- Reuse `tests.lib.server.FrameServer` and `tests.lib.x11`.
- Use a temporary `HOME`, unique display, monotonic deadline, captured logs, and `--noinput`.
- Always close clients and prove SIGTERM removes the socket.
- Cover positive, fragmented, minimum/maximum, malformed, multi-client, cleanup, and reconnect behavior.
- Keep fuzz seeds deterministic and explicitly bounded. Store a seed when it finds a regression.
- Never access DRM, evdev, a live display, root, or a container socket.
- Wall-clock performance results are informational unless a pinned-runner baseline and reviewed tolerance exist.
