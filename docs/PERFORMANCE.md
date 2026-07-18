# Performance and optimization

Optimization is evidence-driven. A desktop server can regress while an isolated instruction gets faster because syscalls, scheduling,
cache footprint, output blocking, memory bandwidth, or branch distribution dominate the workload.

## Workflow

1. Choose a representative scenario and correctness oracle: setup storm, mixed core requests, damage/composite workload, pixel copy,
   input routing, or cleanup churn.
2. Capture environment: commit, binary SHA-256, CPU/microcode, kernel, governor, NASM/binutils, workload, warmup, sample count.
3. Locate the hotspot with whole-process evidence (`perf stat`/`perf record`, syscall counts, or a pinned-runner metric).
4. State a microarchitectural hypothesis: fewer syscalls, shorter dependency chain, better fall-through, smaller hot footprint, fewer
   cache misses, or improved vector/memory throughput.
5. Keep a functional regression test and compare distributions, not one timing.
6. Review code-size, cache, power/wakeup, portability, and maintainability effects before landing.

## Available harness

`make bench-protocol` runs a warmed, bounded headless setup plus RENDER-query workload and writes JSON under
`out/benchmarks/`. It reports min/median/p95/max and the binary hash. It is a smoke benchmark, not a compositor benchmark and not a
PR threshold.

Useful optional tools already common in the environment:

- `perf` for whole-process counters/profiles when permissions allow;
- `llvm-mca` for a carefully extracted straight-line hot region, with CPU model stated;
- `objdump -drwC -Mintel` and `size -A` for instruction/layout and section-size review;
- `strace -c` in a permitted diagnostic environment for syscall count, never as a performance oracle by itself.

## Candidate budgets

Establish reviewed baselines before enforcing numbers. Useful stable budgets include linked file size, `.text`/`.rodata`/`.bss`, idle
wakeups, setup/query p95 on a pinned runner, requests served per fairness quantum, compositor frame time, and cleanup latency. Never
accept a faster path that weakens request validation, client isolation, cleanup, or protocol replies.

## Assembly-specific review

Check instruction latency and reciprocal throughput, loop-carried dependencies, predicted fall-through, fetch/decode bytes, alignment,
data locality, aliasing, and `rep movs/stos` behavior on actual target CPUs. Avoid processor folklore. See `docs/REFERENCE_NOTES.md`.
