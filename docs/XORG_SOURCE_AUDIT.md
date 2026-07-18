# X.Org source audit

Audit date: 2026-07-17. This review used primary X.Org sources and did not copy code into `frame`.

## Audited baselines

- Original MIT X11R1 official archive, released September 1987. The downloaded
  [`X.V11R1.tar.gz`](https://www.x.org/releases/X11R1/X.V11R1.tar.gz) had locally
  computed SHA-256 `6d3640dc815aa7072d9906179953404322a8f5793117268b19323f0ca846fb40`.
  Audited `server/dix/{dispatch,resource,swapreq,swaprep,tables}.c` and
  `server/os/4.2bsd/{connection,io,access,WaitFor}.c`.
- Modern X.Org Server commit `1133421bbd4a0b4064ac0e9565bde8c7034277f1`
  (2026-07-15 checkout): `dix/dispatch.c`, `dix/extension.c`, `dix/resource.c`,
  `dix/swapreq.c`, `os/io.c`, `os/connection.c`, and related headers.
- Modern xorgproto commit `fcb7e9a1a0b593a44740d83b0babddd331fea830`
  (2026-04-17 checkout), including the core, XKB, SHAPE, MIT-SHM, and XTEST specifications.
- Historical X.Org Server 1.12.2 from the official X11R7.7 archive. The audited
  `xorg-server-1.12.2.tar.bz2` matched the published SHA-256
  `ca9f9e22f432f1ccbf8e7a21e746e02be4081a0f3975eb7cff276483193cc5f5`.
- [Current X11 protocol specification](https://www.x.org/releases/current/doc/xproto/x11protocol.pdf)
  and [X11R7.7 source archive](https://www.x.org/releases/X11R7.7/src/xserver/).

The historical and current servers retain the same important design principles even though
implementation details changed: validate request sizes at every handler, explicitly swap
opposite-endian clients, authenticate before entering the running state, scope resources to
clients, and perform centralized teardown.

## Original MIT X11R1 findings

The first X11 server already separated device-independent dispatch, OS transport, resource
ownership, byte swapping, and device-dependent drawing. Its dispatcher used native and swapped
opcode vectors, incremented a per-client sequence before dispatch, converted handler failures to
protocol errors, and closed only the offending client for transport failure. Fixed and variable
handlers pervasively used exact-size or minimum-size checks. `ReadRequestFromClient` kept partial
requests contiguous, capped legacy request size, tracked complete buffered requests, and forced a
yield after ten requests so one client could not own the loop.

The resource layer grouped IDs by client and attached a deletion callback to every record.
`FreeClientResources` removed each record from the live table before invoking its callback because
callbacks could look up other resources during teardown. That ordering is directly relevant to
frame's fixed tables: clear ownership/index visibility before cascading cleanup, but retain any
dependency that a later cleanup step is contractually allowed to inspect.

Several 1987 choices are historical evidence, not safe templates:

- X11R1's `ClientAuthorized` checked protocol version and host access, then read but did not
  authenticate the supplied protocol/data. Its fixed 100-byte auth buffers also lacked a matching
  maximum-length guard. Frame must not call this proof of credential authentication.
- Its Unix listener unconditionally unlinked `/tmp/.X11-unix/XN` before bind. Frame now does the
  safer thing: an existing path fails closed, and a regression proves a second server cannot steal
  an active display. Deliberate ownership/lock/probe logic is required before stale-path recovery.
- Its output path waited synchronously for a slow reader and eventually disconnected it. That is
  bounded compared with an infinite block, but it still stalls the server; frame's target remains
  per-client bounded output queues driven by writable readiness.
- Its 16-bit request-length design predates BIG-REQUESTS. Frame's present legacy cap is compatible
  with that baseline, but every length/count multiplication still needs an explicit overflow and
  payload-shape check.

These findings also explain which parts of the current developer's structure are worth preserving:
small named routines, explicit protocol tables/state, client-local failure, and centralized cleanup
fit the original X11 architecture without requiring frame to reproduce its C layers or unsafe
era-specific assumptions.

## Patterns to adopt

### Request framing and fairness

X.Org's transport path distinguishes partial headers, partial requests, complete requests,
and oversized requests. It checks the words-to-bytes conversion for overflow, caps BigRequests,
keeps each request contiguous for dispatch, and yields so one streaming client cannot monopolize
the server.

For `frame`, every handler needs an explicit equivalent of one of these contracts:

- exact fixed request size;
- at least a fixed header plus a bounded variable payload;
- exact padded size derived from a count or byte length.

The transport-level `CLIENT_BUF_SIZE` cap is necessary but not sufficient: a short request with
a plausible length can still cause a handler to read a field that is not present.

### Byte order

X.Org selects a native or swapped dispatch vector during setup and swaps every request/reply/event
shape consistently. `frame` intentionally supports little-endian clients only. Rejecting a
big-endian setup is safer than partially supporting it; this limitation must remain documented
and regression-tested until a complete swapped-dispatch design exists.

### Authorization

X.Org validates the setup auth protocol/data before it increments the authorized-client count and
enters the running state. `frame` currently drains the fields without checking them, but now limits
the socket to its owner with mode `0700`. This is a defensible single-uid containment boundary, not
X11 credential authentication or cross-user support.

Blocking rule `frame-policy/SEC001` prevents restoring a world-connectable unauthenticated socket.
A production cross-user solution must define one of these approaches and its threat model:

1. MIT-MAGIC-COOKIE-1 with constant-time cookie comparison and secure cookie storage;
2. a securely inherited socket plus verified peer credentials;
3. an explicitly single-user namespace/runtime directory with ownership and mode guarantees.

The current live test proves owner-only mode. Future credential tests must prove missing, malformed,
and incorrect credentials fail before any XID or resource is allocated, while a valid client connects.

### Resource ownership and teardown

X.Org validates new IDs against a client's legal range, performs typed/access-aware lookups, and
centralizes `FreeClientResources`. `frame` already has a strong corresponding structure:

- per-client 2 MiB XID bands;
- `client_cleanup_resources` for windows, pixmaps, GCs, pictures, clips, selection ownership,
  subscriptions, grabs, focus, redirects, and shared-memory attachments;
- slot state reset before reuse.

The missing piece is systematic regression coverage. Each resource class needs a create/disconnect/
reconnect test that proves the record, mapping, subscription, and visible state are gone.

### Replies, errors, and output backpressure

X.Org treats reply-bearing requests as obligations and buffers client output. `frame` correctly
calls out that silently dropping a reply can wedge a client, but some unsupported cases still
fall through to logging or no-op behavior. Each advertised request/extension needs a matrix entry:

- valid reply/event behavior;
- protocol error for invalid resource/value/length;
- deliberate supported no-op only when the protocol defines no reply;
- client-local disconnect only when stream safety cannot be recovered.

Event sends are nonblocking, but ordinary replies are blocking. A client that stops reading can
therefore stall the single-threaded server. Bounded per-client output queues and writable-fd polling
are a reliability goal before multi-user/stable claims.

## Frame strengths retained

- Clear `.bss`, `.rodata`, and `.text` separation with named ABI constants.
- An explicit setup/running state machine and fragmented-input buffering.
- Per-client sequence and resource ranges.
- Comprehensive disconnect cleanup in one routine.
- Owner-only socket permissions plus idempotent signal/socket cleanup in every server mode.
- Nonblocking lossy event delivery and damage/page-flip coalescing.
- Headless framebuffer and synthetic-input paths that support safe protocol development.
- Extensive comments that record desktop-client failure modes and the invariant behind fixes.

These are part of the original developer's style and should be preserved.

## Ordered gaps

| Priority | Gap | Required evidence |
|---|---|---|
| High | Add authenticated cross-user transport without weakening owner-only default | Negative auth tests and threat-model review |
| High | Add exact/minimum/count-derived length validation to every handler | Per-opcode malformed/truncated corpus |
| High | Ensure every reply-bearing request replies or returns an X error | Table-driven request/reply/error tests |
| High | Prevent a non-reading client from blocking all replies | Backpressure and healthy-second-client regression |
| High | Prove all resource classes are reclaimed on disconnect | Create/disconnect/slot-reuse regressions |
| Medium | Add a per-client request work budget for scheduler fairness | Flooding-client versus latency-client test |
| Medium | Return a setup failure reason where practical | Invalid version/order/auth setup fixtures |
| Medium | Document and test fixed table exhaustion behavior | Capacity-boundary and recovery tests |
| Deferred | Full opposite-endian support | Complete swapped request/reply/event coverage |
| Deferred | BIG-REQUESTS | Negotiation, overflow, cap, and large-payload tests |

## Review rule

Use X.Org as a behavioral and defensive reference, not as a requirement to reproduce its C
architecture. Any deliberate deviation must state the simpler `frame` contract, security impact,
compatibility impact, and test oracle in the issue and source comments.
