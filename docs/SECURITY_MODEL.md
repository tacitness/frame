# Security model

## Assets and trust boundaries

| Boundary | Untrusted input | Protected assets |
|---|---|---|
| X11 Unix socket | Setup bytes, request headers/payloads, client timing | Other clients, server availability, mappings, display contents |
| Command line/environment | Display number, flags, `HOME`, inherited descriptors/state | Filesystem paths, selected operating mode, process integrity |
| `~/.framerc` and referenced files | Lengths, tokens, colors, keymaps, paths, raw pixels | Bounded tables, mappings, compositor state |
| Kernel ABI | ioctl/read results, device records, event sizes, identifiers | Memory safety, device state, recoverable display/input |
| SysV shared memory | Client-selected segment ID, size, offset, lifetime | Server address space and other clients' pixels |
| CI/release | Pull-request source, Actions, runner image, scanner databases, artifacts | Repository token, Sonar token, packages, release provenance |

The ordinary threat model includes a malicious local X11 client and malformed input. Hardware tests
also assume device loss, partial acquisition, signal interruption, and unexpected kernel results.

## Required invariants

- One client cannot read, mutate, retain, or receive another client's resources except where the X11
  protocol explicitly mediates shared state.
- Length, count, padding, multiplication, and offset checks happen before memory access.
- A malformed client can be disconnected without terminating or desynchronizing healthy clients.
- Every acquired fd, mapping, framebuffer, master state, shared-memory attachment, and table record
  has one owner and an idempotent reverse-order cleanup path.
- Reply-bearing requests produce a reply or protocol error; output backpressure cannot freeze all clients.
- Hardware state is restored on normal exit and handled explicitly on failure/signal paths.
- CI never supplies untrusted pull-request code to self-hosted machines or protected secrets.
- Versioned git-secrets patterns, redacted Gitleaks, and GitHub push protection are independent required layers.
- Publish authority exists only after build, tests, scans, checksums, quality gate, and artifact transfer.

## Known gaps

### SEC001: X11 authorization

`socket_setup` restricts `/tmp/.X11-unix/XN` to mode `0700`. Setup handling checks little-endian
protocol 11 and drains padded auth fields but does not validate them. The current contract is therefore
single uid: frame and every client run as the same dedicated unprivileged user. The live harness asserts
the socket mode. `frame-policy/SEC001` is a blocking local, CI, and Sonar rule if mode `0777` returns
without an explicit authentication or verified-peer path.

Owner-only mode is containment, not X11 credential authentication. Cross-user support still requires:

1. MIT-MAGIC-COOKIE-1 or securely inherited socket/verified peer credentials;
2. credential creation, storage, rotation, and constant-time validation where applicable;
3. authentication before setup success or XID allocation;
4. a bounded setup-failure reason;
5. missing/wrong/truncated/oversized credential and replay/permission tests;
6. an explicit container and remote-transport policy.

### Request-level validation inventory

The transport buffer caps legacy X11 requests at 262,144 bytes, but handlers do not yet share a
systematic exact/minimum/variable-size check. Audit every dispatched opcode and extension minor against
xorgproto. Add a reusable assembly macro or helper only if its register and error contract stays obvious.

### Blocking output

Events use nonblocking `sendto`, but replies use blocking writes. A non-reading client may stall the
single-threaded server. The target design uses bounded per-client output queues, `POLLOUT`, and an
explicit slow-client disconnect policy.

### Predictable shared paths

The socket path is predictable in a shared sticky directory. Frame never pre-unlinks an existing path: a
second server fails closed instead of stealing a live display, and a regression test proves the first server
remains connectable. Owner-only mode reduces connection exposure but does not solve same-uid denial-of-service
or distinguish a crash-stale path. Add ownership checks and X lock/probe semantics before automatic stale-path
recovery or a stable multi-user claim. Tests use isolated numbers, assert mode `0700`, and prove clean shutdown
leaves no stale path.

## Hardware modes

| Mode | Risk | Automation policy |
|---|---|---|
| Default server with `--noinput` | Unix socket only | Allowed in isolated tests |
| `--fbtest` / `--fbtest2` with `--noinput` | Headless memory/compositor | Allowed when a test explicitly needs it |
| `--probe` / `--probe-input` | Reads device metadata | Manual/diagnostic only |
| `--watch-input` | Captures live input | Human-only; never CI/agent |
| `--display` / `--modeset` | DRM master, scanout, display disruption | Human-controlled TTY acceptance only |

## CI trust model

Untrusted pull requests run on GitHub-hosted disposable runners with `contents: read`, no secrets, and no
hardware. The repo-scoped `frame-ci-build` runner is opt-in and only accepts trusted `main`, tags, and
manual dispatch. Its image must be immutable, unprivileged, daemonless, and have no host devices or sockets.

The Sonar token lives in the protected `sonarqube` environment. Release build jobs have read permission;
the final hosted publish job alone receives package/content/attestation write permissions.

## Review triggers

Require explicit security review for authentication, socket/filesystem permissions, shared memory, resource
ownership, client teardown, request parsing, kernel ABI changes, new syscalls/ioctls, elevated/device access,
runner trust, secrets, workflow permissions, dependencies, and artifact publication.
