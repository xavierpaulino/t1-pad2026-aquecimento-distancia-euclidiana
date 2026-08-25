#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "raw_measurements.csv"
DEFAULT_OUTPUT = ROOT / "data" / "summary.csv"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = ap.parse_args()

    df = pd.read_csv(args.input)
    required = {"N", "T", "batch", "order_position", "repetition", "elapsed_ns", "seed", "checksum"}
    missing = required.difference(df.columns)
    if missing:
        raise SystemExit(f"missing columns: {sorted(missing)}")
    if (df["elapsed_ns"] <= 0).any():
        raise SystemExit("non-positive elapsed time found")
    if df["N"].nunique() != 1:
        raise SystemExit("official dataset violates the requirement that N remain constant")
    expected_t = {32, 64, 128, 256, 512, 1024, 2048, 4096}
    if set(df["T"].unique()) != expected_t:
        raise SystemExit(f"unexpected T set: {sorted(df['T'].unique())}")
    counts = df.groupby("T").size()
    if counts.nunique() != 1:
        raise SystemExit(f"unequal number of measurements across T: {counts.to_dict()}")

    df = df.copy()
    df["time_s"] = df["elapsed_ns"] * 1e-9
    df["vectors_per_s"] = df["N"] / df["time_s"]
    df["elements_per_s"] = (df["N"] * df["T"]) / df["time_s"]
    df["ns_per_element"] = df["elapsed_ns"] / (df["N"] * df["T"])
    # Explicit counting convention: subtract + multiply + accumulate = 3 FLOPs/element.
    df["gflop_per_s_3flop_convention"] = (3.0 * df["N"] * df["T"]) / df["time_s"] / 1e9
    # Logical X payload only; do not interpret this as measured DRAM bandwidth.
    df["x_payload_gb_per_s"] = (8.0 * df["N"] * df["T"]) / df["time_s"] / 1e9

    rows = []
    for (n, t), g in df.groupby(["N", "T"], sort=True):
        time = g["time_s"]
        mean = float(time.mean())
        std = float(time.std(ddof=1)) if len(time) > 1 else 0.0
        rows.append({
            "N": int(n), "T": int(t), "measurements": int(len(g)),
            "mean_time_s": mean, "median_time_s": float(time.median()),
            "std_time_s": std, "cv_time_pct": 100.0 * std / mean if mean else np.nan,
            "min_time_s": float(time.min()), "q1_time_s": float(time.quantile(0.25)),
            "q3_time_s": float(time.quantile(0.75)), "max_time_s": float(time.max()),
            "median_vectors_per_s": float(g["vectors_per_s"].median()),
            "median_elements_per_s": float(g["elements_per_s"].median()),
            "median_ns_per_element": float(g["ns_per_element"].median()),
            "median_gflop_per_s_3flop_convention": float(g["gflop_per_s_3flop_convention"].median()),
            "median_x_payload_gb_per_s": float(g["x_payload_gb_per_s"].median()),
        })
    summary = pd.DataFrame(rows).sort_values("T")

    baseline = float(summary.loc[summary["T"] == summary["T"].min(), "median_time_s"].iloc[0])
    t0 = float(summary["T"].min())
    summary["normalized_median_time"] = summary["median_time_s"] / baseline
    summary["work_ratio_vs_min_T"] = summary["T"] / t0
    summary["time_to_work_ratio"] = summary["normalized_median_time"] / summary["work_ratio_vs_min_T"]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.output, index=False, float_format="%.12g")
    derived = args.output.with_name("measurements_with_metrics.csv")
    df.to_csv(derived, index=False, float_format="%.12g")
    print(f"Wrote {args.output}")
    print(f"Wrote {derived}")


if __name__ == "__main__":
    main()
