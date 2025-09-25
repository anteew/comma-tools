#!/usr/bin/env python3
"""
rlog_to_csv.py — Convert an openpilot rlog(.zst) into a CSV shaped for can_bitwatch.py

Columns:
  window,segment,timestamp,address,bus,data_hex

By default we compute timestamp seconds relative to the first CAN message.
You can mark a window by start time + duration (seconds), and everything else becomes pre/post.

Requires openpilot's LogReader on PYTHONPATH;
either install openpilot next to this script or run from within your openpilot venv.

Examples:
  python rlog_to_csv.py --rlog /path/route/rlog2.zst --window-start 58918.188 \\
    --window-dur 27.399 --out out.csv

"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Optional

from ..utils import add_openpilot_to_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rlog", required=True, help="Path to rlog.zst")
    ap.add_argument("--out", required=True, help="Output CSV path")
    ap.add_argument(
        "--window-start", type=float, default=None, help="Window start (s, relative to first CAN)"
    )
    ap.add_argument(
        "--window-dur",
        type=float,
        default=None,
        help="Window duration (s). If given, marks 'window', otherwise all rows are 'pre'",
    )
    ap.add_argument(
        "--repo-root",
        type=str,
        default=None,
        help="Path to openpilot checkout (to import LogReader)",
    )
    args = ap.parse_args()

    add_openpilot_to_path(args.repo_root)
    try:
        from tools.lib.logreader import LogReader
    except Exception:
        print(
            "ERROR: couldn't import LogReader from openpilot. Pass --repo-root or "
            "run with openpilot on PYTHONPATH.",
            file=sys.stderr,
        )
        raise

    lr = LogReader(args.rlog)
    first_can_ts = None
    rows = []
    for m in lr:
        if m.which() != "can":
            continue
        if first_can_ts is None:
            first_can_ts = m.logMonoTime
        t = (m.logMonoTime - first_can_ts) / 1e9
        for c in m.can:
            addr = c.address
            bus = c.src
            data_hex = c.dat.hex().upper()
            rows.append({"timestamp": t, "address": addr, "bus": bus, "data_hex": data_hex})

    # Segmentation
    def seg_for(t: float) -> str:
        if args.window_start is None or args.window_dur is None:
            return "pre"
        if t < args.window_start:
            return "pre"
        elif t <= args.window_start + args.window_dur:
            return "window"
        else:
            return "post"

    # Write CSV
    with open(args.out, "w", newline="") as f:
        wr = csv.DictWriter(
            f, fieldnames=["window", "segment", "timestamp", "address", "bus", "data_hex"]
        )
        wr.writeheader()
        for r in rows:
            wr.writerow(
                {
                    "window": "1",
                    "segment": seg_for(r["timestamp"]),
                    "timestamp": f"{r['timestamp']:.6f}",
                    "address": f"0x{int(r['address']):03X}",
                    "bus": r["bus"],
                    "data_hex": r["data_hex"],
                }
            )

    print(f"Wrote {args.out} with {len(rows)} rows.")


if __name__ == "__main__":
    main()
