#!/usr/bin/env python3
"""Hardware-free X11 setup/query benchmark with machine-readable output."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.lib.server import FrameServer  # noqa: E402
from tests.lib.x11 import query_extension, recv_exact  # noqa: E402


def percentile(values: list[int], fraction: float) -> int:
    ordered = sorted(values)
    index = min(len(ordered) - 1, int((len(ordered) - 1) * fraction))
    return ordered[index]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", nargs="?", default="./frame", type=Path)
    parser.add_argument("--iterations", type=int, default=250)
    parser.add_argument("--warmup", type=int, default=25)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not 10 <= args.iterations <= 100000:
        parser.error("--iterations must be between 10 and 100000")
    if not 0 <= args.warmup < args.iterations:
        parser.error("--warmup must be non-negative and less than iterations")

    samples: list[int] = []
    with FrameServer(args.binary) as server:
        for index in range(args.iterations):
            start = time.perf_counter_ns()
            connection, _reply = server.connect()
            connection.sendall(query_extension("RENDER"))
            recv_exact(connection, 32)
            connection.close()
            elapsed = time.perf_counter_ns() - start
            if index >= args.warmup:
                samples.append(elapsed)

    result = {
        "schema": 1,
        "benchmark": "headless-setup-render-query",
        "unit": "nanoseconds",
        "iterations": len(samples),
        "warmup": args.warmup,
        "minimum": min(samples),
        "median": int(statistics.median(samples)),
        "p95": percentile(samples, 0.95),
        "maximum": max(samples),
        "binarySha256": __import__("hashlib").sha256(args.binary.read_bytes()).hexdigest(),
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
