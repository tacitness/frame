# Architecture

`frame` is one statically linked Linux x86-64 ELF built from `frame.asm`. It has no libc, allocator, dynamic loader,
or external runtime dependency. The monolithic source is intentional today: constants, fixed state, protocol tables,
dispatch, compositor, kernel backends, and cleanup are directly auditable together.

## Execution flow

```text
_start
  ├─ parse flags and ~/.framerc
  ├─ initialize fixed tables, signals, socket, and optional headless compositor
  └─ serve_loop
       ├─ poll listener, clients, synthetic/real input, hotplug, and DRM completion
       ├─ accept → allocate client slot (SETUP)
       ├─ client_process → frame requests → dispatch core/extension handler
       ├─ route events/replies and coalesce compositor damage
       └─ disconnect/signal → release client or global resources in reverse order
```

Routine CI exercises only the Unix socket and headless memory path. DRM/KMS and evdev are separate manual trust boundaries.

## Memory model

- `.rodata`: logs, names, wire templates, lookup/keymap tables, and immutable constants.
- `.bss`: fixed-capacity client metadata/buffers, windows, pixmaps, graphics contexts, pictures, properties, grabs,
  extension state, and scratch/reply buffers.
- Anonymous/file/shared mappings: framebuffer/backing/pixmap data, wallpaper, and client MIT-SHM attachments.

The current BSS budget is capped at 64 MiB by `scripts/check-elf.sh`; the observed hardened build is about 53.8 MiB.
Fixed capacity avoids allocator complexity but does not remove ownership requirements. Every table has an occupied marker,
capacity, owner or XID range, deterministic exhaustion behavior, and disconnect cleanup obligation.

## Client model

Each of 128 slots contains fd, setup/running state, sequence, and buffered-byte count. Each slot receives a disjoint
2 MiB resource-ID band rooted at `X_RID_BASE`. Setup currently supports little-endian protocol 11.0. Requests use the
legacy 16-bit length, so the per-client 262,144-byte buffer covers the maximum advertised request.

`client_cleanup_resources` is the ownership boundary: it releases resources, mappings, selection state, subscriptions,
grabs, focus, and redirects before the slot is reused. New resource types must be added there and tested.

## Protocol dispatch

Core requests dispatch by opcode; extension requests dispatch by advertised major opcode and minor. Handler design must
not rely on clients being well behaved. The target structure for each handler is:

1. validate request size and count-derived total;
2. validate values, masks, XIDs, ownership, and capacity;
3. stage or acquire state;
4. commit only after all fallible checks/acquisitions pass;
5. send the required reply/event/error;
6. leave enough ownership metadata for disconnect cleanup.

## Display and input modes

- Default plus `--noinput`: socket protocol server, safe automated test mode.
- `--fbtest`/`--fbtest2`: memory-backed compositor and synthetic outputs, suitable for explicit headless tests.
- `--probe` and `--probe-input`: read device metadata; diagnostic/manual.
- `--watch-input`: reads live events; manual only.
- `--display`/`--modeset`: takes display hardware state; TTY/manual only.

See `docs/SECURITY_MODEL.md` for the exact automation boundary.

## Architectural evolution rule

Splitting `frame.asm` is not forbidden, but must solve a measured review/build/ownership problem. A proposal must define
include boundaries, symbol visibility, shared register conventions, dependency direction, generated-table ownership,
link behavior, and migration tests. Mechanical splitting without those contracts increases audit risk.
