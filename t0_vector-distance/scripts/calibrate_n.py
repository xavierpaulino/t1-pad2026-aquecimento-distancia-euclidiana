#!/usr/bin/env python3
"""Choose and validate one N for the official campaign.

The calibration is deliberately separate from the official measurements.
It chooses the largest power-of-two N that keeps the worst-case allocation
(T=4096) inside a configurable fraction of MemAvailable, then validates that
timing overhead from CLOCK_MONOTONIC_RAW is negligible relative to the median
kernel time at T=32.

No absolute minimum kernel duration is assumed. The acceptance criterion is
relative and measured on the actual machine.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import statistics
import subprocess
import tempfile
from pathlib import Path

from cpu_selection import select_cpu, validate_cpu

ROOT = Path(__file__).resolve().parents[1]
BINARY = ROOT / "build" / "vector_distance"
CONFIG = ROOT / "config" / "experiment.conf"
META = ROOT / "config" / "calibration.json"
T_MIN = 32
T_MAX = 4096
BYTES_PER_DOUBLE = 8


def mem_available_bytes() -> int:
    with open("/proc/meminfo", "r", encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) * 1024
    raise RuntimeError("MemAvailable not found in /proc/meminfo")


def bytes_required(n: int, t: int) -> int:
    return BYTES_PER_DOUBLE * (n * t + t + n)


def run_cmd_on_cpu(args: list[str], cpu: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["taskset", "-c", str(cpu), *args],
        check=True,
        text=True,
        capture_output=True,
    )


def timer_probe(cpu: int, samples: int) -> dict[str, int]:
    cp = run_cmd_on_cpu(
        [str(BINARY), "--timer-probe", "--timer-samples", str(samples)], cpu
    )
    line = next((ln for ln in cp.stdout.splitlines() if ln.startswith("TIMER_PROBE")), None)
    if line is None:
        raise RuntimeError(f"timer probe output not understood: {cp.stdout!r}")
    fields: dict[str, int] = {}
    for key, value in re.findall(r"([A-Za-z0-9_]+)=([0-9]+)", line):
        fields[key] = int(value)
    required = {
        "samples", "clock_resolution_ns", "min_positive_delta_ns",
        "median_pair_delta_ns", "p95_pair_delta_ns",
    }
    missing = required - fields.keys()
    if missing:
        raise RuntimeError(f"timer probe missing fields: {sorted(missing)}")
    return fields


def run_probe(n: int, reps: int, warmup: int, seed: int, cpu: int) -> list[int]:
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        path = Path(tmp.name)
    try:
        cmd = [
            str(BINARY), "--n", str(n), "--t", str(T_MIN),
            "--repetitions", str(reps), "--warmup", str(warmup),
            "--seed", str(seed), "--csv", str(path), "--quiet",
        ]
        run_cmd_on_cpu(cmd, cpu)
        values: list[int] = []
        with path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                values.append(int(row["elapsed_ns"]))
        if not values:
            raise RuntimeError("probe produced no timing data")
        return values
    finally:
        path.unlink(missing_ok=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--memory-fraction", type=float, default=0.25,
                    help="maximum fraction of MemAvailable used at T=4096 (default: 0.25)")
    ap.add_argument("--max-timer-overhead-pct", type=float, default=1.0,
                    help="maximum median timer-pair/kernel ratio in percent (default: 1.0)")
    ap.add_argument("--probe-repetitions", type=int, default=15)
    ap.add_argument("--warmup", type=int, default=3)
    ap.add_argument("--timer-samples", type=int, default=100000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--cpu", type=int, default=None)
    args = ap.parse_args()

    if not (0.01 <= args.memory_fraction <= 0.80):
        raise SystemExit("--memory-fraction must be between 0.01 and 0.80")
    if not (0.001 <= args.max_timer_overhead_pct <= 10.0):
        raise SystemExit("--max-timer-overhead-pct must be between 0.001 and 10")
    if args.probe_repetitions < 5:
        raise SystemExit("--probe-repetitions must be >= 5")
    if args.timer_samples < 1000:
        raise SystemExit("--timer-samples must be >= 1000")
    if not BINARY.exists():
        raise SystemExit(f"missing {BINARY}; run 'make release' first")

    cpu_info = validate_cpu(args.cpu) if args.cpu is not None else select_cpu()
    cpu = int(cpu_info["selected_cpu"])
    available = mem_available_bytes()
    budget = int(available * args.memory_fraction)
    max_n = max(1, (budget // BYTES_PER_DOUBLE - T_MAX) // (T_MAX + 1))
    chosen = 1 << int(math.floor(math.log2(max_n))) if max_n >= 1 else 1

    timer = timer_probe(cpu, args.timer_samples)
    kernel_ns = run_probe(chosen, args.probe_repetitions, args.warmup, args.seed, cpu)
    median_kernel_ns = statistics.median(kernel_ns)
    min_kernel_ns = min(kernel_ns)
    max_kernel_ns = max(kernel_ns)
    timer_overhead_pct = 100.0 * timer["median_pair_delta_ns"] / median_kernel_ns
    timer_p95_pct = 100.0 * timer["p95_pair_delta_ns"] / median_kernel_ns

    accepted = timer_overhead_pct <= args.max_timer_overhead_pct
    required = bytes_required(chosen, T_MAX)

    metadata = {
        "chosen_N": chosen,
        "criterion": "largest power-of-two N within memory budget, validated by measured timer/kernel ratio",
        "accepted": accepted,
        "T_min": T_MIN,
        "T_max": T_MAX,
        "memory_fraction": args.memory_fraction,
        "mem_available_bytes_at_calibration": available,
        "memory_budget_bytes": budget,
        "estimated_main_allocation_bytes_at_T4096": required,
        "estimated_fraction_of_memavailable": required / available,
        "probe_repetitions": args.probe_repetitions,
        "probe_warmup": args.warmup,
        "seed": args.seed,
        "cpu": cpu,
        "cpu_selection": cpu_info,
        "timer": timer,
        "T32_kernel_elapsed_ns": kernel_ns,
        "T32_kernel_median_ns": median_kernel_ns,
        "T32_kernel_min_ns": min_kernel_ns,
        "T32_kernel_max_ns": max_kernel_ns,
        "median_timer_pair_overhead_pct_of_T32_kernel": timer_overhead_pct,
        "p95_timer_pair_delta_pct_of_T32_kernel_median": timer_p95_pct,
        "max_allowed_timer_overhead_pct": args.max_timer_overhead_pct,
    }
    META.parent.mkdir(parents=True, exist_ok=True)
    META.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    if not accepted:
        print(f"Calibration rejected: timer overhead ratio {timer_overhead_pct:.6f}% "
              f"exceeds limit {args.max_timer_overhead_pct:.6f}%")
        print(f"Evidence written to {META}")
        raise SystemExit(2)

    CONFIG.write_text(
        "# Generated by scripts/calibrate_n.py; freeze this file for the official campaign.\n"
        f"N={chosen}\n"
        f"SEED={args.seed}\n"
        f"REPETITIONS=30\n"
        f"WARMUP=2\n"
        f"BATCHES=5\n"
        f"CPU={cpu}\n",
        encoding="utf-8",
    )

    print(f"Selected N={chosen}")
    print(f"Pinned CPU={cpu}")
    print(f"CPU selection policy: {cpu_info['selection_policy']}")
    print(f"Physical-core representatives allowed: {cpu_info['physical_core_representatives']}")
    print(f"Selected core logical siblings: {cpu_info['selected_core_logical_siblings']}")
    print(f"Worst-case main allocation at T={T_MAX}: {required / 2**20:.1f} MiB")
    print(f"T=32 median kernel time: {median_kernel_ns / 1e6:.6f} ms")
    print(f"CLOCK_MONOTONIC_RAW nominal resolution: {timer['clock_resolution_ns']} ns")
    print(f"Median back-to-back timer delta: {timer['median_pair_delta_ns']} ns")
    print(f"Timer/kernel median ratio: {timer_overhead_pct:.6f}%")
    print(f"Calibration accepted (limit: {args.max_timer_overhead_pct:.6f}%)")
    print(f"Configuration written to {CONFIG}")
    print(f"Calibration evidence written to {META}")


if __name__ == "__main__":
    main()
