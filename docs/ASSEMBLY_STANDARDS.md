# Assembly standards

These standards formalize the useful style already present in `frame.asm`; they do not demand a wholesale
rewrite or impose high-level-language abstractions on a direct assembly server.

## File and symbol organization

- Begin with the server contract, supported phase/behavior, safe build/run examples, `BITS 64`, and
  `DEFAULT REL`.
- Keep constants grouped by ABI/domain. Named masks, offsets, record sizes, limits, error codes, and syscall
  numbers are preferable to repeated literals.
- Keep writable zero-initialized state in `.bss`, immutable templates/strings/tables in `.rodata`, and
  instructions in `.text`. The linked ELF gate enforces W^X and an NX stack.
- Global labels and data use `snake_case`; constants use `UPPER_SNAKE_CASE`; routine-local labels start with
  a dot. Keep related data and handlers close enough to audit without duplicating definitions.
- Use NASM-derived lengths and offsets when possible. A manually repeated wire length is a regression risk.

## Routine contract

New non-trivial routines should use a header of this form:

```nasm
; parse_example — edi = client slot, rsi = request, edx = request bytes.
; Requires: edx >= fixed header; little-endian wire order.
; Returns: eax = Success/error; preserves rbx/r12, clobbers rcx/r8-r11.
; State: may allocate one record owned by client; rolls it back on failure.
```

The actual local convention may differ, but it must be stated. Review every exit for stack/register balance.
Avoid macros that hide ownership, syscalls, branches, or broad clobber sets.

## Arithmetic and memory

- Zero- or sign-extend deliberately. Match signed versus unsigned branches to the protocol/kernel type.
- Validate a count before `count * element_size`, a dimension before `width * height * bpp`, and an offset
  before `base + offset`. Prove the intermediate width cannot wrap.
- Validate both lower and upper bounds. Reject a negative syscall result before casting it to an unsigned count.
- Check request size before the first field load. For variable data, validate the padded total and the logical
  count independently.
- Keep source/destination ranges clear before `rep movs*`; use `memmove`-style direction where overlap is possible.
- Fixed BSS capacity is a design decision. Exhaustion needs a deterministic protocol error or client-local failure,
  not overwrite or reuse of a live slot.

## Syscalls and kernel ABI

- Use the x86-64 `syscall` ABI only. State syscall number and argument registers through named constants/comments.
- Treat `rax < 0` as `-errno`; handle short reads/writes and `EINTR`/`EAGAIN` where the fd mode permits them.
- Derive ioctl values from authoritative headers/specification and record structure size/layout assumptions.
- Acquisition paths need one reverse-order cleanup path. Record whether an fd/mapping/master/object is live so
  partial failure and signal cleanup are idempotent.
- Do not use privileged CPU instructions, self-modifying code, executable stack/data, or writable/executable mappings.

## X11 handlers

For every core opcode and extension minor, record:

- exact/minimum request bytes and count-derived payload formula;
- valid enum/mask/resource ownership;
- reply, error, event, or protocol-defined void behavior;
- per-client sequence behavior;
- records/mappings allocated and disconnect cleanup;
- happy, boundary, malformed, multi-client, and cleanup tests.

Advertising an extension is a compatibility promise. Do not list an extension merely to get a client past startup
if a reply-bearing mandatory request can still deadlock it.

## Comments and maintainability

The existing strongest comments explain a real failure and why the invariant fixes it. Continue that style. Remove
stale phase claims and comments when behavior changes. Avoid comments that only translate the next instruction.

Generated tables must name their source, generation command/script, ordering, encoding, fallback rules, and a test
that catches drift. Do not hand-edit a generated range without updating its source process.

## Optimization

Do not substitute shorter or theoretically lower-latency instructions without a measured server workload. Consider
instruction bytes, decode, dependency chains, branch direction, data/cache layout, syscalls, and readability together.
See `docs/PERFORMANCE.md` and `docs/REFERENCE_NOTES.md`.
