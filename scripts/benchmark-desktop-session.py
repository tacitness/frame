#!/usr/bin/env python3
"""Compare matched tswm/xterm sessions on frame and a nested X server."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import random
import re
import shutil
import signal
import statistics
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CLOCK_TICKS = int(os.sysconf("SC_CLK_TCK"))
COUNTER_FIELDS = (
    "userTicks",
    "systemTicks",
    "minorFaults",
    "majorFaults",
    "voluntaryContextSwitches",
    "involuntaryContextSwitches",
    "readSyscalls",
    "writeSyscalls",
    "readBytes",
    "writeBytes",
    "cancelledWriteBytes",
    "runTimeNanoseconds",
    "runqueueWaitNanoseconds",
    "timeslices",
)
MEMORY_FIELDS = (
    "rssKiB",
    "pssKiB",
    "privateKiB",
    "sharedKiB",
    "anonymousKiB",
    "swapKiB",
    "anonHugePagesKiB",
    "peakRssKiB",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_text(path: Path, default: str = "") -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return default


def parse_colon_file(path: Path) -> dict[str, int]:
    values: dict[str, int] = {}
    for line in read_text(path).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        token = value.strip().split()
        if token and token[0].lstrip("-").isdigit():
            values[key] = int(token[0])
    return values


def process_snapshot(pid: int) -> dict[str, int]:
    proc = Path("/proc") / str(pid)
    stat = read_text(proc / "stat")
    closing = stat.rfind(")")
    if closing < 0:
        raise ProcessLookupError(pid)
    fields = stat[closing + 2 :].split()
    if len(fields) < 20:
        raise ProcessLookupError(pid)

    status = parse_colon_file(proc / "status")
    io = parse_colon_file(proc / "io")
    smaps = parse_colon_file(proc / "smaps_rollup")
    schedstat = read_text(proc / "schedstat").split()
    try:
        fd_count = sum(1 for _entry in (proc / "fd").iterdir())
    except OSError:
        fd_count = 0

    return {
        "userTicks": int(fields[11]),
        "systemTicks": int(fields[12]),
        "minorFaults": int(fields[7]),
        "majorFaults": int(fields[9]),
        "voluntaryContextSwitches": status.get("voluntary_ctxt_switches", 0),
        "involuntaryContextSwitches": status.get("nonvoluntary_ctxt_switches", 0),
        "readSyscalls": io.get("syscr", 0),
        "writeSyscalls": io.get("syscw", 0),
        "readBytes": io.get("read_bytes", 0),
        "writeBytes": io.get("write_bytes", 0),
        "cancelledWriteBytes": io.get("cancelled_write_bytes", 0),
        "runTimeNanoseconds": int(schedstat[0]) if len(schedstat) >= 1 else 0,
        "runqueueWaitNanoseconds": int(schedstat[1]) if len(schedstat) >= 2 else 0,
        "timeslices": int(schedstat[2]) if len(schedstat) >= 3 else 0,
        "rssKiB": smaps.get("Rss", status.get("VmRSS", 0)),
        "pssKiB": smaps.get("Pss", 0),
        "privateKiB": smaps.get("Private_Clean", 0) + smaps.get("Private_Dirty", 0),
        "sharedKiB": smaps.get("Shared_Clean", 0) + smaps.get("Shared_Dirty", 0),
        "anonymousKiB": smaps.get("Anonymous", 0),
        "swapKiB": smaps.get("Swap", 0),
        "anonHugePagesKiB": smaps.get("AnonHugePages", 0),
        "peakRssKiB": status.get("VmHWM", 0),
        "threads": status.get("Threads", 0),
        "fileDescriptors": fd_count,
    }


def group_snapshot(pids: list[int]) -> dict[str, Any]:
    totals = {field: 0 for field in (*COUNTER_FIELDS, *MEMORY_FIELDS)}
    totals.update({"threads": 0, "fileDescriptors": 0})
    live: list[int] = []
    for pid in sorted(set(pids)):
        try:
            snapshot = process_snapshot(pid)
        except (OSError, ProcessLookupError):
            continue
        live.append(pid)
        for field in totals:
            totals[field] += snapshot[field]
    if not live:
        raise ProcessLookupError(f"no live processes from {pids}")
    return {"pids": live, "processCount": len(live), **totals}


def interval_metrics(
    before: dict[str, Any], after: dict[str, Any], seconds: float
) -> dict[str, Any]:
    delta = {
        field: max(0, int(after[field]) - int(before[field]))
        for field in COUNTER_FIELDS
    }
    user_seconds = delta["userTicks"] / CLOCK_TICKS
    system_seconds = delta["systemTicks"] / CLOCK_TICKS
    cpu_seconds = user_seconds + system_seconds
    result: dict[str, Any] = {
        "wallSeconds": seconds,
        "cpuPercent": cpu_seconds * 100.0 / seconds,
        "cpuSeconds": cpu_seconds,
        "userCpuSeconds": user_seconds,
        "systemCpuSeconds": system_seconds,
        "minorFaults": delta["minorFaults"],
        "majorFaults": delta["majorFaults"],
        "minorFaultsPerSecond": delta["minorFaults"] / seconds,
        "majorFaultsPerSecond": delta["majorFaults"] / seconds,
        "voluntaryContextSwitches": delta["voluntaryContextSwitches"],
        "involuntaryContextSwitches": delta["involuntaryContextSwitches"],
        "contextSwitchesPerSecond": (
            delta["voluntaryContextSwitches"]
            + delta["involuntaryContextSwitches"]
        )
        / seconds,
        "readSyscalls": delta["readSyscalls"],
        "writeSyscalls": delta["writeSyscalls"],
        "ioSyscallsPerSecond": (
            delta["readSyscalls"] + delta["writeSyscalls"]
        )
        / seconds,
        "readBytes": delta["readBytes"],
        "writeBytes": delta["writeBytes"],
        "cancelledWriteBytes": delta["cancelledWriteBytes"],
        "runqueueWaitSeconds": delta["runqueueWaitNanoseconds"] / 1_000_000_000,
        "timeslices": delta["timeslices"],
        "timeslicesPerSecond": delta["timeslices"] / seconds,
        "processCount": after["processCount"],
        "threads": after["threads"],
        "fileDescriptors": after["fileDescriptors"],
    }
    for field in MEMORY_FIELDS:
        result[field] = after[field]
    return result


def descendants(pid: int) -> list[int]:
    found: list[int] = []
    pending = [pid]
    while pending:
        parent = pending.pop()
        children_text = read_text(
            Path("/proc") / str(parent) / "task" / str(parent) / "children"
        )
        children = [int(token) for token in children_text.split() if token.isdigit()]
        found.extend(children)
        pending.extend(children)
    return found


def process_name(pid: int) -> str:
    return read_text(Path("/proc") / str(pid) / "comm").strip()


def wait_until(predicate: Any, timeout: float, description: str) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise TimeoutError(f"timed out waiting for {description}")


def terminate_process(process: subprocess.Popen[Any] | None) -> None:
    if process is None or process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=3)


def available_display() -> int:
    start = random.SystemRandom().randrange(2000, 50000)
    for offset in range(512):
        candidate = 2000 + ((start - 2000 + offset) % 48000)
        if not Path(f"/tmp/.X11-unix/X{candidate}").exists():
            return candidate
    raise RuntimeError("no isolated X11 display is available")


@dataclass
class DesktopSession:
    backend: str
    frame_binary: Path
    tswm_binary: Path
    tswm_profile: Path
    host_display: str
    server_cpu: int
    client_cpu: int
    active_seconds: float
    temporary: tempfile.TemporaryDirectory[str] = field(init=False)
    root: Path = field(init=False)
    home: Path = field(init=False)
    display_number: int = field(init=False)
    display: str = field(init=False)
    socket_path: Path = field(init=False)
    server: subprocess.Popen[Any] | None = field(default=None, init=False)
    tswm: subprocess.Popen[Any] | None = field(default=None, init=False)
    active_xterm: subprocess.Popen[Any] | None = field(default=None, init=False)
    log_handles: list[Any] = field(default_factory=list, init=False)
    server_log: Path = field(init=False)
    tswm_log: Path = field(init=False)
    default_xterm_pid: int = field(init=False)
    startup: dict[str, float] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="frame-desktop-bench-")
        self.root = Path(self.temporary.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.display_number = available_display()
        self.display = f":{self.display_number}"
        self.socket_path = Path(f"/tmp/.X11-unix/X{self.display_number}")
        self.server_log = self.root / "server.log"
        self.tswm_log = self.root / "tswm.log"

    def _log_handle(self, path: Path) -> Any:
        handle = path.open("wb")
        self.log_handles.append(handle)
        return handle

    def _spawn(
        self,
        command: list[str],
        environment: dict[str, str],
        log_path: Path,
        cpu: int,
    ) -> subprocess.Popen[Any]:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=self._log_handle(log_path),
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        os.sched_setaffinity(process.pid, {cpu})
        return process

    def start(self) -> None:
        environment = os.environ.copy()
        environment.update({"HOME": str(self.home), "LC_ALL": "C"})
        server_environment = environment.copy()
        started = time.perf_counter()
        if self.backend == "frame":
            command = [
                str(self.frame_binary),
                str(self.display_number),
                "--fbtest",
                "--noinput",
            ]
            server_environment["DISPLAY"] = self.display
        elif self.backend == "xephyr":
            command = [
                shutil.which("Xephyr") or "Xephyr",
                self.display,
                "-br",
                "-noreset",
                "-nolisten",
                "tcp",
                "-screen",
                "1920x1080",
            ]
            server_environment["DISPLAY"] = self.host_display
        else:
            raise ValueError(f"unknown backend: {self.backend}")
        self.server = self._spawn(
            command, server_environment, self.server_log, self.server_cpu
        )

        def server_ready() -> bool:
            if self.server and self.server.poll() is not None:
                raise RuntimeError(
                    f"{self.backend} server exited:\n{read_text(self.server_log)[-4000:]}"
                )
            return self.socket_path.is_socket()

        wait_until(server_ready, 10, f"{self.backend} X socket {self.socket_path}")
        ready = time.perf_counter()
        self.startup["serverReadyMs"] = (ready - started) * 1000

        client_environment = environment.copy()
        client_environment["DISPLAY"] = self.display
        tswm_started = time.perf_counter()
        self.tswm = self._spawn(
            [
                str(self.tswm_binary),
                "--run",
                "--profile",
                str(self.tswm_profile),
                "--display",
                self.display,
            ],
            client_environment,
            self.tswm_log,
            self.client_cpu,
        )

        def client_mapped() -> bool:
            if self.tswm and self.tswm.poll() is not None:
                raise RuntimeError(
                    f"tswm exited on {self.backend}:\n{read_text(self.tswm_log)[-4000:]}"
                )
            return "map-request:" in read_text(self.tswm_log)

        wait_until(client_mapped, 15, f"tswm xterm map on {self.backend}")
        mapped = time.perf_counter()
        self.startup["tswmToClientMappedMs"] = (mapped - tswm_started) * 1000
        self.startup["coldDesktopReadyMs"] = (mapped - started) * 1000

        def find_default_xterm() -> bool:
            assert self.tswm is not None
            matches = [
                pid
                for pid in descendants(self.tswm.pid)
                if process_name(pid) == "xterm"
            ]
            if matches:
                self.default_xterm_pid = matches[0]
                return True
            return False

        wait_until(find_default_xterm, 5, f"default xterm process on {self.backend}")

    def component_pids(self, active: bool) -> dict[str, list[int]]:
        assert self.server is not None
        assert self.tswm is not None
        terminal_pids = [self.default_xterm_pid]
        if active and self.active_xterm is not None:
            terminal_pids.append(self.active_xterm.pid)
        return {
            "server": [self.server.pid],
            "tswm": [self.tswm.pid],
            "terminal": terminal_pids,
            "session": [self.server.pid, self.tswm.pid, *terminal_pids],
        }

    def measure(self, seconds: float, active: bool = False) -> dict[str, Any]:
        components = self.component_pids(active)
        before = {name: group_snapshot(pids) for name, pids in components.items()}
        started = time.perf_counter()
        time.sleep(seconds)
        elapsed = time.perf_counter() - started
        after = {name: group_snapshot(pids) for name, pids in components.items()}
        return {
            name: interval_metrics(before[name], after[name], elapsed)
            for name in components
        }

    def start_active_terminal(self) -> Path:
        assert self.tswm is not None
        marker = self.root / "start-workload"
        prior_maps = read_text(self.tswm_log).count("map-request:")
        generator = (
            "import pathlib,sys,time;"
            "p=pathlib.Path(sys.argv[1]);"
            "d=float(sys.argv[2]);"
            "\nwhile not p.exists(): time.sleep(0.01)"
            "\nend=time.monotonic()+d"
            "\ni=0"
            "\nwhile time.monotonic()<end:"
            "\n print(f'frame desktop workload {i:06d} 0123456789abcdef' * 2);"
            " sys.stdout.flush(); i+=1; time.sleep(0.01)"
            "\ntime.sleep(2)"
        )
        environment = os.environ.copy()
        environment.update(
            {"HOME": str(self.home), "DISPLAY": self.display, "LC_ALL": "C"}
        )
        self.active_xterm = self._spawn(
            [
                shutil.which("xterm") or "xterm",
                "-geometry",
                "100x30",
                "-title",
                "frame-desktop-benchmark",
                "-e",
                sys.executable,
                "-u",
                "-c",
                generator,
                str(marker),
                str(self.active_seconds),
            ],
            environment,
            self.root / "active-xterm.log",
            self.client_cpu,
        )

        def active_mapped() -> bool:
            if self.active_xterm and self.active_xterm.poll() is not None:
                raise RuntimeError(
                    f"active xterm exited on {self.backend}:\n"
                    f"{read_text(self.root / 'active-xterm.log')[-4000:]}"
                )
            return read_text(self.tswm_log).count("map-request:") > prior_maps

        wait_until(active_mapped, 10, f"active xterm map on {self.backend}")
        time.sleep(0.25)
        return marker

    def frame_counters(self) -> dict[str, int] | None:
        if self.backend != "frame" or self.server is None:
            return None
        before = read_text(self.server_log).count("FBSTATE back=")
        os.kill(self.server.pid, signal.SIGUSR1)
        wait_until(
            lambda: read_text(self.server_log).count("FBSTATE back=") > before,
            5,
            "frame compositor counter dump",
        )
        matches = re.findall(
            r"FBSTATE back=(\d+)\s+(\d+)\s+blit=(\d+)\s+"
            r"fill=(\d+)\s+flush=(\d+)\s+evdrop=(\d+)",
            read_text(self.server_log),
        )
        if not matches:
            return None
        back, recomposites, blit, fill, flush, dropped = map(int, matches[-1])
        return {
            "backBuffer": back,
            "recomposites": recomposites,
            "pixelsBlitted": blit,
            "pixelsFilled": fill,
            "bytesFlushed": flush,
            "eventsDropped": dropped,
        }

    def unhandled_opcodes(self) -> dict[str, int]:
        if self.backend != "frame":
            return {}
        counts: dict[str, int] = {}
        for opcode in re.findall(r"req opcode=(\d+)", read_text(self.server_log)):
            counts[opcode] = counts.get(opcode, 0) + 1
        return counts

    def close(self) -> None:
        terminate_process(self.active_xterm)
        terminate_process(self.tswm)
        terminate_process(self.server)
        for handle in self.log_handles:
            handle.close()
        self.log_handles.clear()
        if self.socket_path.exists():
            self.socket_path.unlink(missing_ok=True)
        self.temporary.cleanup()


def numeric_distribution(values: list[float | int]) -> dict[str, float]:
    return {
        "minimum": min(values),
        "median": statistics.median(values),
        "mean": statistics.fmean(values),
        "maximum": max(values),
    }


def summarize(runs: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for backend in ("frame", "xephyr"):
        selected = [run for run in runs if run["backend"] == backend]
        backend_summary: dict[str, Any] = {"startup": {}, "idle": {}, "active": {}}
        for key in selected[0]["startup"]:
            backend_summary["startup"][key] = numeric_distribution(
                [run["startup"][key] for run in selected]
            )
        for phase in ("idle", "active"):
            for component in selected[0][phase]:
                component_summary: dict[str, Any] = {}
                for metric, value in selected[0][phase][component].items():
                    if isinstance(value, (int, float)):
                        component_summary[metric] = numeric_distribution(
                            [run[phase][component][metric] for run in selected]
                        )
                backend_summary[phase][component] = component_summary
        result[backend] = backend_summary

    comparisons: dict[str, Any] = {"startup": {}, "idle": {}, "active": {}}
    for key in result["frame"]["startup"]:
        frame_value = result["frame"]["startup"][key]["median"]
        xephyr_value = result["xephyr"]["startup"][key]["median"]
        comparisons["startup"][key] = comparison(frame_value, xephyr_value)
    for phase in ("idle", "active"):
        for component in ("server", "session"):
            comparisons[phase][component] = {}
            for metric in result["frame"][phase][component]:
                frame_value = result["frame"][phase][component][metric]["median"]
                xephyr_value = result["xephyr"][phase][component][metric]["median"]
                comparisons[phase][component][metric] = comparison(
                    frame_value, xephyr_value
                )
    result["comparisonFrameVsXephyr"] = comparisons
    return result


def comparison(frame_value: float, xephyr_value: float) -> dict[str, float | None]:
    delta = frame_value - xephyr_value
    return {
        "frameMedian": frame_value,
        "xephyrMedian": xephyr_value,
        "absoluteDelta": delta,
        "deltaPercent": (delta * 100.0 / xephyr_value) if xephyr_value else None,
    }


def git_value(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def environment_record(
    args: argparse.Namespace, server_cpu: int, client_cpu: int
) -> dict[str, Any]:
    cpu_model = "unknown"
    for line in read_text(Path("/proc/cpuinfo")).splitlines():
        if line.startswith("model name") and ":" in line:
            cpu_model = line.split(":", 1)[1].strip()
            break
    governors = sorted(
        {
            read_text(path).strip()
            for path in Path("/sys/devices/system/cpu").glob(
                "cpu[0-9]*/cpufreq/scaling_governor"
            )
            if read_text(path).strip()
        }
    )
    return {
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "hostname": platform.node(),
        "kernel": platform.release(),
        "machine": platform.machine(),
        "cpuModel": cpu_model,
        "allowedCpus": sorted(os.sched_getaffinity(0)),
        "serverCpu": server_cpu,
        "clientCpu": client_cpu,
        "governors": governors,
        "loadAverage": list(os.getloadavg()),
        "hostDisplay": args.host_display,
        "frameBinary": str(args.frame_binary),
        "frameSha256": sha256(args.frame_binary),
        "tswmBinary": str(args.tswm_binary),
        "tswmSha256": sha256(args.tswm_binary),
        "tswmProfile": str(args.tswm_profile),
        "tswmProfileSha256": sha256(args.tswm_profile),
        "gitCommit": git_value("rev-parse", "HEAD"),
        "dirtyPathCount": len(git_value("status", "--porcelain").splitlines()),
        "xephyrVersion": subprocess.run(
            [shutil.which("Xephyr") or "Xephyr", "-version"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        ).stdout.strip(),
        "perfEventParanoid": read_text(Path("/proc/sys/kernel/perf_event_paranoid")).strip(),
        "ptraceScope": read_text(Path("/proc/sys/kernel/yama/ptrace_scope")).strip(),
    }


def run_sample(args: argparse.Namespace, backend: str, sample: int) -> dict[str, Any]:
    allowed = sorted(os.sched_getaffinity(0))
    server_cpu = allowed[0]
    client_cpu = allowed[1] if len(allowed) > 1 else allowed[0]
    session = DesktopSession(
        backend=backend,
        frame_binary=args.frame_binary,
        tswm_binary=args.tswm_binary,
        tswm_profile=args.tswm_profile,
        host_display=args.host_display,
        server_cpu=server_cpu,
        client_cpu=client_cpu,
        active_seconds=args.active_seconds,
    )
    try:
        session.start()
        time.sleep(args.settle_seconds)
        idle = session.measure(args.idle_seconds)
        marker = session.start_active_terminal()
        components = session.component_pids(active=True)
        before = {name: group_snapshot(pids) for name, pids in components.items()}
        marker.touch()
        started = time.perf_counter()
        time.sleep(args.active_seconds)
        elapsed = time.perf_counter() - started
        after = {name: group_snapshot(pids) for name, pids in components.items()}
        active = {
            name: interval_metrics(before[name], after[name], elapsed)
            for name in components
        }
        counters = session.frame_counters()
        return {
            "sample": sample,
            "backend": backend,
            "display": session.display,
            "startup": session.startup,
            "idle": idle,
            "active": active,
            "frameCompositorCounters": counters,
            "unhandledOpcodes": session.unhandled_opcodes(),
        }
    finally:
        session.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run matched tswm/xterm sessions on frame --fbtest and Xephyr; "
            "emit raw samples plus median comparisons."
        )
    )
    parser.add_argument("--frame-binary", type=Path, default=ROOT / "frame")
    parser.add_argument(
        "--tswm-binary", type=Path, default=ROOT.parent / "tswm/target/debug/tswm"
    )
    parser.add_argument(
        "--tswm-profile",
        type=Path,
        default=ROOT.parent / "tswm/profiles/human-session.profile.json",
    )
    parser.add_argument("--host-display", default=os.environ.get("DISPLAY", ""))
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--settle-seconds", type=float, default=0.75)
    parser.add_argument("--idle-seconds", type=float, default=2.0)
    parser.add_argument("--active-seconds", type=float, default=3.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    args.frame_binary = args.frame_binary.resolve()
    args.tswm_binary = args.tswm_binary.resolve()
    args.tswm_profile = args.tswm_profile.resolve()
    if not 1 <= args.samples <= 50:
        parser.error("--samples must be between 1 and 50")
    if not 0 <= args.settle_seconds <= 30:
        parser.error("--settle-seconds must be between 0 and 30")
    if not 0.5 <= args.idle_seconds <= 120:
        parser.error("--idle-seconds must be between 0.5 and 120")
    if not 1 <= args.active_seconds <= 120:
        parser.error("--active-seconds must be between 1 and 120")
    for path in (args.frame_binary, args.tswm_binary, args.tswm_profile):
        if not path.exists():
            parser.error(f"required path does not exist: {path}")
    if not args.host_display:
        parser.error("--host-display (or DISPLAY) is required for Xephyr")
    if not shutil.which("Xephyr") or not shutil.which("xterm"):
        parser.error("Xephyr and xterm are required")

    allowed = sorted(os.sched_getaffinity(0))
    server_cpu = allowed[0]
    client_cpu = allowed[1] if len(allowed) > 1 else allowed[0]
    runs: list[dict[str, Any]] = []
    for sample in range(1, args.samples + 1):
        order = ("frame", "xephyr") if sample % 2 else ("xephyr", "frame")
        for backend in order:
            print(
                f"sample {sample}/{args.samples}: starting {backend}",
                file=sys.stderr,
                flush=True,
            )
            run = run_sample(args, backend, sample)
            runs.append(run)
            server_active = run["active"]["server"]
            print(
                f"sample {sample}/{args.samples}: {backend} active "
                f"cpu={server_active['cpuPercent']:.2f}% "
                f"pss={server_active['pssKiB']} KiB",
                file=sys.stderr,
                flush=True,
            )

    result = {
        "schema": 1,
        "benchmark": "matched-tswm-xterm-desktop-session",
        "samplesPerBackend": args.samples,
        "geometry": "1920x1080",
        "settleSeconds": args.settle_seconds,
        "idleSeconds": args.idle_seconds,
        "activeSeconds": args.active_seconds,
        "workload": {
            "windowManager": "tswm",
            "idleTerminal": "xterm from human-session profile",
            "activeTerminal": "xterm 100x30, 100 fixed text lines/second",
            "frameMode": "--fbtest --noinput",
            "baseline": "nested Xephyr on the supplied host display",
            "viewerBridgeIncluded": False,
        },
        "environment": environment_record(args, server_cpu, client_cpu),
        "measurementNotes": [
            "CPU and fault counters are /proc/<pid>/stat deltas.",
            "RSS/PSS/private/shared values are post-interval smaps_rollup totals.",
            "Read/write syscall counts are /proc/<pid>/io syscr/syscw, not all syscalls.",
            "Context switches and scheduler timeslices are wakeup-pressure proxies.",
            "Xephyr includes nested presentation to the host X server; frame fbtest renders to anonymous buffers.",
            "The ffplay read-only preview bridge and SIGUSR1 dumps are outside timed intervals.",
        ],
        "runs": runs,
        "summary": summarize(runs),
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
