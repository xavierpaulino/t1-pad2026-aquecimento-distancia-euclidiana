#!/usr/bin/env python3
"""Deterministic CPU selection for the single-thread benchmark.

Policy:
  1. consider only CPUs in the current process affinity mask;
  2. collapse SMT siblings to one representative per physical core;
  3. prefer a physical core whose representative is not logical CPU 0;
  4. choose deterministically by (package, core, cpu).

This deliberately avoids selecting a CPU from instantaneous utilization: doing so
would make calibration and the official campaign depend on transient system load.
The selected CPU is frozen in config/experiment.conf and reused unchanged.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

SYS_CPU = Path("/sys/devices/system/cpu")


def _read_int(path: Path) -> int | None:
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def cpu_topology(cpu: int) -> dict[str, int | None]:
    topo = SYS_CPU / f"cpu{cpu}" / "topology"
    return {
        "cpu": cpu,
        "package": _read_int(topo / "physical_package_id"),
        "core": _read_int(topo / "core_id"),
    }


def allowed_cpus() -> list[int]:
    try:
        cpus = sorted(os.sched_getaffinity(0))
    except AttributeError as exc:
        raise RuntimeError("sched_getaffinity is unavailable on this platform") from exc
    if not cpus:
        raise RuntimeError("process affinity mask contains no CPUs")
    return cpus


def select_cpu() -> dict[str, object]:
    allowed = allowed_cpus()
    topology = [cpu_topology(cpu) for cpu in allowed]

    # One deterministic representative per physical core. If topology data is
    # unavailable, fall back to one entry per logical CPU rather than guessing.
    representatives: dict[tuple[object, ...], dict[str, int | None]] = {}
    for entry in topology:
        package = entry["package"]
        core = entry["core"]
        if package is None or core is None:
            key = ("logical", entry["cpu"])
        else:
            key = ("physical", package, core)
        current = representatives.get(key)
        if current is None or int(entry["cpu"]) < int(current["cpu"]):
            representatives[key] = entry

    candidates = sorted(
        representatives.values(),
        key=lambda e: (
            e["package"] if e["package"] is not None else 10**9,
            e["core"] if e["core"] is not None else 10**9,
            int(e["cpu"]),
        ),
    )

    nonzero = [entry for entry in candidates if int(entry["cpu"]) != 0]
    selected = nonzero[0] if nonzero else candidates[0]

    siblings = [
        int(e["cpu"])
        for e in topology
        if e["package"] is not None
        and e["core"] is not None
        and e["package"] == selected["package"]
        and e["core"] == selected["core"]
    ]

    return {
        "selected_cpu": int(selected["cpu"]),
        "selection_policy": "deterministic_physical_core_representative_avoid_cpu0",
        "allowed_cpus": allowed,
        "physical_core_representatives": [int(e["cpu"]) for e in candidates],
        "selected_package": selected["package"],
        "selected_core": selected["core"],
        "selected_core_logical_siblings": siblings,
    }


def validate_cpu(cpu: int) -> dict[str, object]:
    info = select_cpu()
    allowed = set(int(x) for x in info["allowed_cpus"])
    if cpu not in allowed:
        raise RuntimeError(f"CPU {cpu} is not in the current allowed affinity mask: {sorted(allowed)}")
    topo = cpu_topology(cpu)
    return {
        "selected_cpu": cpu,
        "selection_policy": "explicit_user_cpu",
        "allowed_cpus": sorted(allowed),
        "physical_core_representatives": info["physical_core_representatives"],
        "selected_package": topo["package"],
        "selected_core": topo["core"],
        "selected_core_logical_siblings": [
            int(e["cpu"])
            for e in (cpu_topology(c) for c in sorted(allowed))
            if e["package"] is not None
            and e["core"] is not None
            and e["package"] == topo["package"]
            and e["core"] == topo["core"]
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cpu", type=int, default=None, help="validate and report an explicit CPU")
    ap.add_argument("--json", action="store_true", help="emit JSON")
    args = ap.parse_args()
    info = validate_cpu(args.cpu) if args.cpu is not None else select_cpu()
    if args.json:
        print(json.dumps(info, indent=2))
    else:
        print(info["selected_cpu"])


if __name__ == "__main__":
    main()
