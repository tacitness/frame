# Local reference notes

These notes paraphrase the locally available books; they are not substitutes for reading the
source. Page numbers refer to the PDF page labels/contents where practical. No book text is copied
into the codebase.

## Agner Fog: Optimizing subroutines in assembly language

Local source: `IT/optimization_manuals/optimizing_assembly.pdf`, 2023-06-22 edition.

- Pages 7-10: decide the purpose and interfaces before writing assembly; organize difficult code
  into logical units and establish a repeated white-box, boundary, illegal-input, and randomized
  test strategy. For `frame`, each protocol handler should have a documented wire/state contract
  and independent fixtures.
- Pages 27-32: calling/register conventions are part of an interface. `frame` has no compiler to
  enforce one, so routine headers and review must state inputs, outputs, clobbers, and stack rules.
- Pages 59-68: find real hotspots first; understand latency versus throughput, dependency chains,
  instruction-fetch limits, and likely branch direction. Use this for compositor/pixel/input hot
  paths only after representative profiling.
- Pages 72-87: code size, address forms, alignment, and cache layout interact. Alignment or
  unrolling without measurement may increase cache pressure and regress the full server.
- Pages 87-103: optimize loops by identifying the actual bottleneck and moving invariant work, not
  by blindly unrolling. Protocol-table walks need bounds and correctness before tuning.
- Pages 134-152: instruction choice is microarchitecture-dependent; string instructions and other
  seemingly compact operations need measurement on target CPUs.
- Pages 152-154: benchmarks need warmup, repeated samples, CPU/context controls, and awareness of
  cache/branch-predictor effects. An isolated microbenchmark does not prove whole-server speed.

Resulting policy: `make bench-protocol` is informational. A regression threshold requires a pinned
runner, reviewed workload, distribution, tolerance, and repeat confirmation.

## Ed Jorgensen: x86-64 Assembly Language Programming with Ubuntu

Local source: `IT/Assembly/assembly64.pdf`, version 1.1.44 (May 2022).

- Chapters 4-5 (pages 33-52): explicit constants and `.data`/`.bss`/`.text` structure make assembly
  and linker behavior understandable. `frame` keeps the same separation and checks the linked ELF.
- Chapter 7 (pages 71-125): operand width, signedness, flags, and control flow must be intentional.
  Reviews recompute comparisons and extension/truncation at every wire/kernel boundary.
- Chapter 10 (pages 155-162): separate algorithm design, implementation, test/debug, and error
  classification. An assembly patch should not discover its contract while being coded.
- Chapters 11 onward: macros and procedures can make repeated invariants explicit, but hidden
  clobbers or over-general macros make low-level code harder to audit. Keep interfaces narrow.

## Jonathan Bartlett: Programming from the Ground Up

Local source: `IT/Assembly/ProgrammingGroundUp-1-0-lettersize.pdf` (2003).

- Chapters 3-5: plan control flow and understand files/buffers before coding.
- Chapter 7 (pages 87-93): robust programs treat error handling as part of the algorithm.
- Chapter 9 (pages 109-132): memory layout and allocation ownership are essential to correctness.
  For `frame`, fixed BSS tables and `mmap` backings still need explicit lifetime and capacity rules.
- Chapter 12 (pages 167-172): decide when and where optimization is worthwhile before local tuning.

## David A. Wheeler: Programming Secure Applications for Unix-like Systems

Local source: `IT/Programming_Secure_Applications_for_Unix_like_Systems.pdf` (March 2003).

- Pages 3-6: define assets, trust, and security objectives; validate against an allowlist and check
  numeric minimums, maximums, encodings, and lengths.
- Pages 9-10: command-line values, environment, config contents, descriptors, signals, IPC, and
  filesystem state are inputs—not implicit truths.
- Pages 12-16: assembly provides no automatic bounds protection. Size checks must precede writes
  and count/size arithmetic must be overflow-safe.
- Pages 17-22: minimize privilege, choose secure defaults, fail safely, avoid shared-directory
  races, and perform complete mediation. These directly govern the X socket and hardware paths.
- Pages 24-26: validate outbound system-call parameters, check every return, and avoid leaking
  unnecessary internal detail to untrusted peers.

Resulting policy: routine CI is unprivileged and hardware-free; X11 authorization is a blocker;
temporary paths and inherited state receive explicit tests; malformed input affects only its client.
