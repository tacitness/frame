---
description: 'NASM, syscall, X11 protocol, and low-level performance standards'
applyTo: '**/*.asm'
---

# Assembly instructions

Follow `AGENTS.md` and `docs/ASSEMBLY_STANDARDS.md`.

- Preserve `BITS 64`, `DEFAULT REL`, section separation, four-space indentation, and local-label style.
- Document routine register contracts and keep every push/pop balanced across all exits.
- Validate the complete fixed/variable request size before loading any field. Use overflow-safe count and padding arithmetic.
- Validate client ownership and capacity before creating or mutating an XID-backed record.
- Check negative syscall results before consuming outputs. Cleanup must be idempotent and reverse partial acquisition.
- Reply-bearing requests must reply or return a protocol error; a silent drop can deadlock the client.
- Add a focused regression for every changed protocol or resource-lifecycle path.
- Optimize only a measured hotspot. Record CPU, workload, samples, distribution, code-size impact, and regression tests.

Never suggest privileged instructions, executable writable memory, `int 0x80`, direct hardware tests, or an unaudited raw literal ABI.
