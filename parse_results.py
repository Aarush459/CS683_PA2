#!/usr/bin/env python3
"""
parse_results.py -- Extract ChampSim statistics for CS683 PA2 and produce
summary tables (CSV + printed table) and bar plots in the style of the PA2 PDF.

Expected layout (as produced by run_task1a.sh):
    <results_dir>/<config>/<TraceN>.txt      e.g. results/baseline/Trace1.txt

Usage:
    python3 parse_results.py <results_dir> <baseline_cfg> [<cfg> ...]

Examples:
    python3 parse_results.py results baseline ip_stride          # Task 1A
    python3 parse_results.py results baseline ip_stride spp      # Task 1B

Every number is read from the "Region of Interest Statistics" section of the
ChampSim output, i.e. the 25M simulated instructions after the 25M warmup.

Metric definitions (from the PA2 PDF):
    Speedup        = IPC(config) / IPC(baseline, no prefetching)
    L1D Load MPKI  = taken directly from the "L1D LOAD ... MPKI" stat
    Accuracy       = taken directly from the "ACCURACY" field ChampSim prints
    Coverage       = (L1D load misses baseline - L1D load misses config)
                     / L1D load misses baseline
L2C load / instruction / data MPKI are also extracted for use in Tasks 2 and 3.
"""
import csv
import math
import os
import re
import sys

NUM = r"([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?|-?nan|-?inf)"

DISPLAY = {"baseline": "Baseline", "ip_stride": "IP-stride", "spp": "SPP"}


def label(cfg):
    return DISPLAY.get(cfg, cfg)


def parse_file(path):
    """Return a dict of statistics parsed from one ChampSim output file."""
    with open(path) as f:
        text = f.read()

    # Only use the ROI section so heartbeat / warmup lines are never matched.
    parts = text.split("Region of Interest Statistics", 1)
    if len(parts) < 2:
        raise ValueError(f"{path}: no 'Region of Interest Statistics' section "
                         f"(did the run finish?)")
    roi = parts[1]

    def grab(pattern, cast=float):
        m = re.search(pattern, roi)  # no DOTALL: each pattern stays on one line
        if not m:
            raise ValueError(f"{path}: could not find pattern {pattern!r}")
        return [cast(g) for g in m.groups()] if len(m.groups()) > 1 else cast(m.group(1))

    s = {}
    s["ipc"] = grab(r"CPU 0 cumulative IPC:\s*" + NUM)
    s["instructions"] = grab(r"CPU 0 cumulative IPC:\s*\S+\s+instructions:\s*(\d+)", int)

    # L1D demand loads
    s["l1d_load_access"] = grab(r"L1D LOAD\s+ACCESS:\s*(\d+)", int)
    s["l1d_load_miss"] = grab(r"L1D LOAD\s+ACCESS:.*?MISS:\s*(\d+)", int)
    s["l1d_load_mpki"] = grab(r"L1D LOAD\s+ACCESS:.*?MPKI:\s*" + NUM)

    # L1D prefetch counters
    (s["pf_requested"], s["pf_issued"], s["pf_useful"], s["pf_useless"]) = grab(
        r"L1D PREFETCH\s+REQUESTED:\s*(\d+)\s+ISSUED:\s*(\d+)\s+"
        r"USEFUL:\s*(\d+)\s+USELESS:\s*(\d+)", int)
    s["accuracy"] = grab(r"L1D USEFUL LOAD PREFETCHES:.*?ACCURACY:\s*" + NUM)

    # L2C load MPKIs (needed for Tasks 2 and 3)
    s["l2c_load_mpki"] = grab(r"L2C LOAD\s+ACCESS:.*?MPKI:\s*" + NUM)
    s["l2c_instr_load_mpki"] = grab(r"L2C INSTRUCTION LOAD MPKI:\s*" + NUM)
    s["l2c_data_load_mpki"] = grab(r"L2C DATA LOAD MPKI:\s*" + NUM)
    return s


def natural_key(name):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", name)]


def collect(results_dir, configs):
    """Parse every <results_dir>/<cfg>/<trace>.txt for the given configs."""
    base_dir = os.path.join(results_dir, configs[0])
    traces = sorted((f[:-4] for f in os.listdir(base_dir) if f.endswith(".txt")),
                    key=natural_key)
    data = {}
    for cfg in configs:
        for t in traces:
            path = os.path.join(results_dir, cfg, t + ".txt")
            if not os.path.exists(path):
                print(f"WARNING: missing {path}, skipped")
                continue
            data[(t, cfg)] = parse_file(path)
    return traces, data


def add_derived(traces, configs, data):
    """Speedup and coverage are relative to the baseline (first config)."""
    base = configs[0]
    for t in traces:
        b = data.get((t, base))
        if b is None:
            continue
        for cfg in configs:
            s = data.get((t, cfg))
            if s is None:
                continue
            s["speedup"] = s["ipc"] / b["ipc"]
            s["coverage_pct"] = (100.0 * (b["l1d_load_miss"] - s["l1d_load_miss"])
                                 / b["l1d_load_miss"])


COLUMNS = ["ipc", "speedup", "l1d_load_mpki", "l1d_load_miss", "coverage_pct",
           "pf_requested", "pf_issued", "pf_useful", "pf_useless", "accuracy",
           "l2c_load_mpki", "l2c_instr_load_mpki", "l2c_data_load_mpki"]


def write_csv(path, traces, configs, data):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["trace", "config"] + COLUMNS)
        for t in traces:
            for cfg in configs:
                s = data.get((t, cfg))
                if s:
                    w.writerow([t, cfg] + [s.get(c, "") for c in COLUMNS])


def print_table(traces, configs, data):
    cols = ["ipc", "speedup", "l1d_load_mpki", "accuracy", "coverage_pct"]
    head = ["Trace", "Config", "IPC", "Speedup", "L1D Load MPKI",
            "Accuracy", "Coverage (%)"]
    print("| " + " | ".join(head) + " |")
    print("|" + "---|" * len(head))
    for t in traces:
        for cfg in configs:
            s = data.get((t, cfg))
            if not s:
                continue
            vals = []
            for c in cols:
                v = s.get(c, float("nan"))
                vals.append("-" if (cfg == configs[0] and c in ("accuracy", "coverage_pct"))
                            else f"{v:.4f}")
            print(f"| {t} | {label(cfg)} | " + " | ".join(vals) + " |")


def grouped_bars(ax, traces, cfgs, values, colors, fmt="%.2f"):
    import numpy as np
    x = np.arange(len(traces))
    width = 0.8 / len(cfgs)
    for i, cfg in enumerate(cfgs):
        bars = ax.bar(x + (i - (len(cfgs) - 1) / 2) * width, values[cfg], width,
                      label=label(cfg), color=colors[i % len(colors)], edgecolor="grey")
        ax.bar_label(bars, fmt=fmt, fontsize=7, padding=2)  # print value on each bar
    ax.set_xticks(x)
    ax.set_xticklabels(traces)


def make_plots(out_dir, traces, configs, data):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    os.makedirs(out_dir, exist_ok=True)
    others = configs[1:]
    if not others:
        print("Only the baseline was given; no comparison plots made.")
        return

    def series(cfg, key):
        out = []
        for t in traces:
            v = data.get((t, cfg), {}).get(key, float("nan"))
            out.append(0.0 if (v is None or math.isnan(v)) else v)
        return out

    blues = ["#6a7fb8", "#93abc6", "#3b5a8c", "#b7c7dc"]
    mpki_colors = ["lightcoral", "skyblue", "lightgreen", "khaki"]

    # Speedup over baseline
    fig, ax = plt.subplots(figsize=(7, 4.5))
    vals = {c: series(c, "speedup") for c in others}
    grouped_bars(ax, traces, others, vals, blues, fmt="%.4f")
    ax.axhline(1.0, color="brown", linestyle="--", linewidth=1, label="Baseline")
    allv = [v for c in others for v in vals[c]] + [1.0]
    # Zoom the y-axis around 1.0 so small speedups/slowdowns stay visible
    pad = max((max(allv) - min(allv)) * 0.5, 0.002)
    ax.set_ylim(min(allv) - pad, max(allv) + pad)
    ax.set_ylabel("Speedup")
    ax.set_title("Speedup of L1D Prefetchers over Baseline (no prefetching)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "speedup.png"), dpi=150)
    plt.close(fig)

    # L1D load MPKI (baseline included)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    vals = {c: series(c, "l1d_load_mpki") for c in configs}
    grouped_bars(ax, traces, configs, vals, mpki_colors)
    ax.set_ylabel("L1D Load MPKI")
    ax.set_xlabel("Traces")
    ax.set_title("L1D Load MPKI")
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "l1d_load_mpki.png"), dpi=150)
    plt.close(fig)

    # Accuracy and coverage (prefetching configs only).
    # ChampSim prints ACCURACY already as a percentage
    # (= USEFUL LOAD PREFETCHES / PREFETCH ISSUED TO LOWER LEVEL * 100).
    for key, ylabel, fname in [("accuracy", "L1D Prefetch Accuracy (%)", "accuracy.png"),
                               ("coverage_pct", "L1D Prefetch Coverage (%)", "coverage.png")]:
        fig, ax = plt.subplots(figsize=(7, 4.5))
        vals = {c: series(c, key) for c in others}
        grouped_bars(ax, traces, others, vals, blues)
        ax.set_ylabel(ylabel)
        ax.set_title(ylabel)
        ax.legend()
        fig.tight_layout()
        fig.savefig(os.path.join(out_dir, fname), dpi=150)
        plt.close(fig)

    print(f"Plots written to {out_dir}/")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    results_dir, configs = sys.argv[1], sys.argv[2:]
    traces, data = collect(results_dir, configs)
    add_derived(traces, configs, data)

    tag = "_".join(configs)
    csv_path = os.path.join(results_dir, f"summary_{tag}.csv")
    write_csv(csv_path, traces, configs, data)
    print(f"CSV written to {csv_path}\n")
    print_table(traces, configs, data)
    print()
    make_plots(os.path.join(results_dir, f"plots_{tag}"), traces, configs, data)


if __name__ == "__main__":
    main()
