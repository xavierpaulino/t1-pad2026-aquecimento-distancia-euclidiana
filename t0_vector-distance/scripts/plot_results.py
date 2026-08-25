#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "data" / "summary.csv"
RAW_METRICS = ROOT / "data" / "measurements_with_metrics.csv"
OUTDIR = ROOT / "results"


def save_line(x, y, ylabel, filename, yscale=None):
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    ax.plot(x, y, marker="o", linewidth=1.5)
    ax.set_xscale("log", base=2)
    if yscale:
        ax.set_yscale(yscale)
    ax.set_xlabel("Vector size T (elements)")
    ax.set_ylabel(ylabel)
    ax.set_xticks(list(x))
    ax.set_xticklabels([str(int(v)) for v in x])
    ax.grid(True, which="major", alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUTDIR / f"{filename}.pdf", bbox_inches="tight")
    fig.savefig(OUTDIR / f"{filename}.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", type=Path, default=SUMMARY)
    ap.add_argument("--measurements", type=Path, default=RAW_METRICS)
    args = ap.parse_args()

    summary = pd.read_csv(args.summary).sort_values("T")
    obs = pd.read_csv(args.measurements)
    OUTDIR.mkdir(parents=True, exist_ok=True)

    save_line(summary["T"], summary["median_time_s"], "Median execution time (s)", "execution_time")
    save_line(summary["T"], summary["median_vectors_per_s"] / 1e6, "Median throughput (million vectors/s)", "vectors_per_second")
    save_line(summary["T"], summary["median_elements_per_s"] / 1e9, "Median throughput (billion elements/s)", "elements_per_second")
    save_line(summary["T"], summary["median_ns_per_element"], "Median time per element (ns/element)", "ns_per_element")

    # Variability: raw execution-time distributions, one box per T.
    ts = list(summary["T"].astype(int))
    box_data = [obs.loc[obs["T"] == t, "time_s"].to_numpy() for t in ts]
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    ax.boxplot(box_data, tick_labels=[str(t) for t in ts], showfliers=True)
    ax.set_xlabel("Vector size T (elements)")
    ax.set_ylabel("Execution time (s)")
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUTDIR / "execution_time_variability.pdf", bbox_inches="tight")
    fig.savefig(OUTDIR / "execution_time_variability.png", dpi=220, bbox_inches="tight")
    plt.close(fig)

    # Compare observed time growth with growth in amount of work.
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    ax.plot(summary["T"], summary["normalized_median_time"], marker="o", label="Observed median time")
    ax.plot(summary["T"], summary["work_ratio_vs_min_T"], marker="s", linestyle="--", label="Work ratio T/32")
    ax.set_xscale("log", base=2)
    ax.set_yscale("log", base=2)
    ax.set_xlabel("Vector size T (elements)")
    ax.set_ylabel("Normalized ratio (baseline T=32)")
    ax.set_xticks(ts)
    ax.set_xticklabels([str(t) for t in ts])
    ax.grid(True, which="major", alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUTDIR / "normalized_scaling.pdf", bbox_inches="tight")
    fig.savefig(OUTDIR / "normalized_scaling.png", dpi=220, bbox_inches="tight")
    plt.close(fig)

    print(f"Plots written to {OUTDIR}")


if __name__ == "__main__":
    main()
