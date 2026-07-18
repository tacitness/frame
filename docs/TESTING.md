# Testing strategy

The harness is layered so most defects are proven without hardware and so new protocol tests reuse one safe lifecycle.

## Commands

| Layer | Command | Purpose | Hardware |
|---|---|---|---|
| Unit | `make test-unit` | Wire encoding/padding, policy, metadata, roadmap consistency | None |
| Static/ELF | `make test-static` | ELF64/static/NX/W^X/sections/relocations/build-ID/BSS contract | None |
| Integration | `make test-integration` | Live setup, fragmentation, extensions, multi-client flow | None |
| Regression | `make test-regression` | Named prior/high-risk failures and auth-tail framing | None |
| Bounded fuzz corpus | `make test-fuzz` | Deterministic malformed setup seeds and server containment | None |
| Reproducibility | `make test-reproducible` | Byte-identical clean native builds | None |
| Quality | `make quality` | Text, NASM, shell/YAML/Actions, all tests, reproducibility | None |
| Security | `make ci-local` | Quality plus secrets and offline security checks | None |
| Performance | `make bench-protocol` | Informational setup/query latency distribution | None |
| Hardware acceptance | Manual checklist | DRM/KMS, evdev, VT, hotplug, recovery | Explicit human control |

`tests/lib/server.py` owns process, temporary home, display selection, logs, timeouts, SIGTERM, and stale-socket checks.
`tests/lib/x11.py` owns wire fixtures/parsing. Extend those helpers instead of creating a second lifecycle or codec.

## Required dimensions for each request

Each supported core opcode and extension minor eventually needs these cases, where applicable:

1. correct fixed/variable request and exact reply/event fields;
2. fragmented header and payload across multiple reads;
3. minimum, maximum, empty, and padded counts;
4. declared length shorter/longer than fields or payload;
5. multiplication/addition overflow and table-capacity boundary;
6. invalid enum, mask, XID, type, ownership, or lifecycle state;
7. correct protocol error and sequence number;
8. pipelined requests in one read without stream desynchronization;
9. two clients with overlapping-looking local IDs but isolated server ranges;
10. disconnect during/after allocation, healthy-client survival, cleanup, and slot reuse;
11. slow/non-reading client versus healthy-client progress for reply/event paths;
12. advertised-extension negotiation followed by every mandatory reply-bearing request.

## Current automated coverage

- Little-endian setup, fragmented byte-by-byte.
- Setup reply version, vendor, roots, request limit, and 24/32-bit pixmap formats.
- RENDER `QueryExtension` present and unknown extension absent.
- Simultaneous clients receive disjoint resource-ID bases.
- Invalid byte order and protocol major close only the offending client.
- Padded setup auth fields are framed/drained correctly, and the unauthenticated socket remains owner-only (`0700`).
- Bounded invalid setup corpus, reconnect, SIGTERM, and socket cleanup.
- Hardened static ELF and byte-reproducible build.

This is a foundation, not X11 conformance. The highest-value next harness work is table-driven request-length/error coverage,
resource-class disconnect/slot-reuse tests, output-backpressure isolation, and differential setup/core behavior against Xvfb/Xorg.

## Regression test rule

A defect is not fixed until a test fails against the known-bad behavior and passes against the fix. Name the issue or invariant
in the test. Keep the smallest reproducing wire fixture as a permanent corpus case. Do not assert only “server did not crash” when
the protocol defines a reply, error, state transition, or cleanup result.

## Fuzzing path

The checked-in corpus is deterministic and PR-safe. Future structured fuzzing should generate valid and invalid X11 shapes from
protocol metadata, cap every request/run, isolate one disposable server, preserve failing seeds, and verify a healthy second client.
Do not run unbounded random fuzzing in pre-commit. Direct-syscall assembly cannot rely on language sanitizers; use protocol oracles,
guarded test environments, crash/core capture, and static/ELF checks.

## Manual hardware tests

Read `tests/manual/README.md`. Hardware results must record machine/GPU/kernel, active display manager/VT state, exact command,
expected recovery, observed stderr, and post-test device/display health. Never convert these tests into a self-hosted workflow.

## Test environment caveat

Some sandboxes prohibit binding Unix sockets in `/tmp/.X11-unix`. In that case pure unit/static tests still run, while live protocol
tests must run in an approved isolated environment. An `EPERM` bind is an environment limitation and must not be reported as a pass.
