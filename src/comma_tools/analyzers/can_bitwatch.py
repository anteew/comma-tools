#!/usr/bin/env python3
"""
can_bitwatch.py — Swiss‑army analyzer for CSV dumps of CAN frames with segment labels.
Danny/Friday edition.
Inputs:
  CSV with columns: window,segment,timestamp,address,bus,data_hex
    - segment in {"pre","window","post"} (case-insensitive)
    - timestamp in seconds (float, absolute); we compute relative to window start for mm:ss.mmm
    - address is hex like "0x027" or decimal; we normalize to int
    - data_hex is 0–8 bytes, MSB-first (e.g., "00 00 00 00 20 02 00 00" or "0000000020020000")
Outputs (by default to <output_prefix>.*):
  - counts.csv: address × (pre, window, post, delta)
  - per_address.json: per-address notes (unique payload counts per segment; top payloads)
  - bit_edges.csv: all detected bit edges for watched bits, with timings and labels
  - candidates_window_only.csv: bits that toggle only inside the window
  - accel_hunt.csv: results of "3 pulses ~2s each" search (±0.5s tolerance)
Usage:
  python can_bitwatch.py --csv in.csv --output-prefix analysis \
      --watch 0x027:B4b5 0x027:B5b1 0x67A:B3b7 0x321:B5b1
Tip:
  Use together with rlog_to_csv.py to generate the CSV from an rlog.zst.
"""
from __future__ import annotations
import argparse, csv, re, math, sys, json, os
from collections import defaultdict, Counter
from dataclasses import dataclass
from typing import Tuple, List, Dict, Iterable

SEG_PRE, SEG_WIN, SEG_POST = "pre", "window", "post"


def parse_hex_bytes(s: str) -> bytes:
    s = s.strip().replace(" ", "").replace("0x", "").replace(",", "")
    if len(s) % 2 == 1:
        s = "0" + s
    if s == "":
        return b""
    return bytes.fromhex(s)


def norm_address(s: str) -> int:
    s = s.strip()
    if s.lower().startswith("0x"):
        return int(s, 16)
    try:
        return int(s)
    except ValueError:
        # Allow bare hex without 0x
        return int(s, 16)


def msb_label_to_indices(label: str) -> Tuple[int, int, int]:
    """
    Convert "B4b5" (MSB-first bit naming) to (byte_idx, msb_bit, lsb_bit).
    B<number> b<number>, both 0-indexed. MSB b7..b0.
    Example: B4b5 -> byte=4, msb=5, lsb=2
    """
    m = re.fullmatch(r"B(\d+)b(\d+)", label.strip())
    if not m:
        raise ValueError(f"Bad MSB label: {label}")
    byte = int(m.group(1))
    msb_bit = int(m.group(2))
    if not (0 <= msb_bit <= 7):
        raise ValueError("MSB bit out of range 0..7")
    lsb_bit = 7 - msb_bit
    return byte, msb_bit, lsb_bit


def global_idx_from_msb(byte_idx: int, msb_bit: int) -> int:
    lsb = 7 - msb_bit
    return byte_idx * 8 + lsb


@dataclass
class WatchBit:
    addr: int
    byte: int
    msb: int
    lsb: int
    gidx: int

    @classmethod
    def from_spec(cls, spec: str) -> "WatchBit":
        # spec like "0x027:B4b5"
        if ":" not in spec:
            raise ValueError(f"Bad watch spec (missing ':'): {spec}")
        a, lbl = spec.split(":", 1)
        addr = norm_address(a)
        byte, msb, lsb = msb_label_to_indices(lbl)
        gidx = global_idx_from_msb(byte, msb)
        return cls(addr, byte, msb, lsb, gidx)


def fmt_time_rel(seconds: float) -> str:
    m = int(seconds // 60)
    s = seconds - 60 * m
    return f"{m:02d}:{s:06.3f}"


def payload_to_u64_le(payload: bytes) -> int:
    b = payload + b"\x00" * (8 - len(payload)) if len(payload) < 8 else payload[:8]
    return int.from_bytes(b, "little")


def bit_value(u64: int, gidx: int) -> int:
    return (u64 >> gidx) & 1


def read_csv_rows(path: str):
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            seg = row.get("segment", "").strip().lower()
            if seg not in (SEG_PRE, SEG_WIN, SEG_POST):
                # try to infer segment if not provided (optional)
                seg = row.get("seg", "").strip().lower()
                if seg not in (SEG_PRE, SEG_WIN, SEG_POST):
                    raise ValueError(f"Row missing/invalid segment: {row}")
            ts = float(row["timestamp"])
            addr = norm_address(row["address"])
            bus = int(row.get("bus", 0))
            data_hex = row.get("data_hex", "") or row.get("data", "")
            payload = parse_hex_bytes(data_hex)
            win = row.get("window", "1").strip()
            yield {
                "window": win,
                "segment": seg,
                "timestamp": ts,
                "address": addr,
                "bus": bus,
                "payload": payload,
            }


def analyze_counts(rows):
    counts = defaultdict(lambda: Counter({SEG_PRE: 0, SEG_WIN: 0, SEG_POST: 0}))
    for r in rows:
        counts[r["address"]][r["segment"]] += 1
    # Compute delta = window - max(pre, post)
    out = []
    for addr, c in sorted(counts.items()):
        pre, win, post = c[SEG_PRE], c[SEG_WIN], c[SEG_POST]
        delta = win - max(pre, post)
        out.append(
            {"address": f"0x{addr:03X}", "pre": pre, "window": win, "post": post, "delta": delta}
        )
    return out


def analyze_per_address(rows, topn=5):
    by_addr_seg = defaultdict(lambda: defaultdict(list))  # addr -> seg -> list of payload hex
    for r in rows:
        by_addr_seg[r["address"]][r["segment"]].append(r["payload"])

    notes = {}
    for addr, seg_map in by_addr_seg.items():
        addr_key = f"0x{addr:03X}"
        notes[addr_key] = {}
        for seg, payloads in seg_map.items():
            hexes = ["".join(f"{b:02X}" for b in p) for p in payloads]
            uniq = Counter(hexes)
            top = uniq.most_common(topn)
            notes[addr_key][seg] = {"unique_payloads": len(uniq), "top_payloads": top}
    return notes


def detect_edges_and_candidates(rows, watch: List[WatchBit], window_start: float | None):
    # Build per-address timelines of payload u64
    rows_sorted = sorted(rows, key=lambda r: r["timestamp"])
    first_ts = rows_sorted[0]["timestamp"] if rows_sorted else 0.0
    # If no explicit window start provided, infer as first "window" ts
    if window_start is None:
        win_rows = [r for r in rows_sorted if r["segment"] == SEG_WIN]
        window_start = win_rows[0]["timestamp"] if win_rows else first_ts

    # State trackers
    last_u64_by_addr: dict[int, int] = {}
    last_bit_by_addr_gidx: dict[int, dict[int, int]] = defaultdict(
        lambda: {}
    )  # addr -> {gidx: last_bit}
    edges = []  # for watched bits
    toggles_by_bit = defaultdict(list)  # (addr,gidx) -> list[timestamp]

    for r in rows_sorted:
        addr = r["address"]
        u64 = payload_to_u64_le(r["payload"])
        if addr in last_u64_by_addr:
            prev = last_u64_by_addr[addr]
            changed = u64 ^ prev
            if changed:
                # For all 0..63 bits, record toggles
                for gidx in range(64):
                    if (changed >> gidx) & 1:
                        toggles_by_bit[(addr, gidx)].append(r["timestamp"])
        last_u64_by_addr[addr] = u64

        # Log watched edges
        for wb in watch:
            if wb.addr != addr:
                continue
            bit = bit_value(u64, wb.gidx)
            last = last_bit_by_addr_gidx[addr].get(wb.gidx, bit)
            if bit != last:
                edges.append(
                    {
                        "address": f"0x{addr:03X}",
                        "byte": wb.byte,
                        "msb_bit": wb.msb,
                        "lsb_bit": wb.lsb,
                        "global_idx": wb.gidx,
                        "timestamp": r["timestamp"],
                        "rel": fmt_time_rel(max(0.0, r["timestamp"] - window_start)),
                        "edge": f"{last}->{bit}",
                        "segment": r["segment"],
                    }
                )
            last_bit_by_addr_gidx[addr][wb.gidx] = bit

    # Candidates: bits that toggle only in window (and at least once)
    candidates = []
    for (addr, gidx), times in toggles_by_bit.items():
        segs = set()
        for t in times:
            # Find segment by nearest row (approx)
            # We can just infer by comparing to window start and end from rows
            pass
        # We'll compute segment lookup using nearest row timestamp
        # Build index:
    # Build timestamp->segment quick map (approx by latest <= t)
    ts_seg = []
    for r in rows_sorted:
        ts_seg.append((r["timestamp"], r["segment"]))
    ts_seg.sort()

    def seg_at(t: float) -> str:
        # binary search latest ts <= t
        lo, hi = 0, len(ts_seg) - 1
        if hi < 0:
            return SEG_PRE
        if t < ts_seg[0][0]:
            return ts_seg[0][1]
        while lo <= hi:
            mid = (lo + hi) // 2
            if ts_seg[mid][0] <= t:
                lo = mid + 1
            else:
                hi = mid - 1
        return ts_seg[max(0, hi)][1]

    for (addr, gidx), times in toggles_by_bit.items():
        segs = {seg_at(t) for t in times}
        if segs == {SEG_WIN}:
            candidates.append(
                {"address": f"0x{addr:03X}", "global_idx": gidx, "toggles": len(times)}
            )

    return edges, candidates, window_start


def hunt_accel_pulses(rows, candidates, window_start, window_end=None, pulse_sec=2.0, tol=0.5):
    """
    For each candidate bit, reconstruct its on/off timeline and look for exactly three ~2s high pulses.
    """
    rows_sorted = sorted(rows, key=lambda r: r["timestamp"])
    if window_end is None:
        # infer window end as last "window" timestamp
        win_ts = [r["timestamp"] for r in rows_sorted if r["segment"] == SEG_WIN]
        window_end = (
            max(win_ts) if win_ts else (rows_sorted[-1]["timestamp"] if rows_sorted else 0.0)
        )

    def bit_series(addr, gidx):
        series = []  # (t, bit)
        last_val = 0
        seen = False
        for r in rows_sorted:
            if r["address"] != addr:
                continue
            u64 = payload_to_u64_le(r["payload"])
            bit = (u64 >> gidx) & 1
            if not seen:
                last_val = bit
                seen = True
            if bit != last_val:
                series.append((r["timestamp"], bit))
                last_val = bit
        return series

    out = []
    for cand in candidates:
        addr = int(cand["address"], 16)
        gidx = cand["global_idx"]
        series = bit_series(addr, gidx)
        # Build pulse durations inside window: rising (0->1) to falling (1->0)
        pulses = []
        state = 0
        t_rise = None
        # Determine starting state at window_start
        # Replay until window_start
        curr = 0
        t_last = 0.0
        for t, b in series:
            if t <= window_start:
                curr = b
                t_last = t
                continue
            break
        state = curr
        for t, b in series:
            if t < window_start:
                continue
            if t > window_end:
                break
            if state == 0 and b == 1:
                t_rise = t
                state = 1
            elif state == 1 and b == 0:
                if t_rise is not None:
                    dur = t - t_rise
                    pulses.append(dur)
                t_rise = None
                state = 0
        # If still high at window_end, close pulse
        if state == 1 and t_rise is not None and window_end > window_start:
            pulses.append(window_end - t_rise)

        # Evaluate
        def approx_eq(d):
            return (pulse_sec - tol) <= d <= (pulse_sec + tol)

        valid = (len(pulses) == 3) and all(approx_eq(d) for d in pulses)
        out.append(
            {
                "address": f"0x{addr:03X}",
                "global_idx": gidx,
                "pulses": [round(d, 3) for d in pulses],
                "valid_three_2s": bool(valid),
            }
        )
    return out


def main():
    ap = argparse.ArgumentParser(description="Analyze CAN CSV for cruise bits & ACCEL pulses")
    ap.add_argument("--csv", required=True, help="Input CSV path")
    ap.add_argument("--output-prefix", default="analysis", help="Prefix for output files")
    ap.add_argument(
        "--window-start",
        type=float,
        default=None,
        help="Override window start time (s) for mm:ss.mmm",
    )
    ap.add_argument(
        "--watch",
        nargs="*",
        default=["0x027:B4b5", "0x027:B5b1", "0x67A:B3b7", "0x321:B5b1"],
        help="Watch specs like '0x027:B4b5'",
    )
    args = ap.parse_args()

    rows = list(read_csv_rows(args.csv))
    # Counts & notes (use full generator twice -> convert to list)
    counts = analyze_counts(rows)
    notes = analyze_per_address(rows)

    # Watch bits
    watch = [WatchBit.from_spec(s) for s in args.watch]
    edges, candidates, win_start = detect_edges_and_candidates(rows, watch, args.window_start)
    accel = hunt_accel_pulses(rows, candidates, win_start)

    # Write outputs
    op = args.output_prefix
    os.makedirs(os.path.dirname(op) if os.path.dirname(op) else ".", exist_ok=True)

    with open(f"{op}.counts.csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=["address", "pre", "window", "post", "delta"])
        wr.writeheader()
        wr.writerows(counts)

    with open(f"{op}.per_address.json", "w") as f:
        json.dump(notes, f, indent=2)

    with open(f"{op}.bit_edges.csv", "w", newline="") as f:
        wr = csv.DictWriter(
            f,
            fieldnames=[
                "address",
                "byte",
                "msb_bit",
                "lsb_bit",
                "global_idx",
                "timestamp",
                "rel",
                "edge",
                "segment",
            ],
        )
        wr.writeheader()
        wr.writerows(edges)

    with open(f"{op}.candidates_window_only.csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=["address", "global_idx", "toggles"])
        wr.writeheader()
        wr.writerows(candidates)

    with open(f"{op}.accel_hunt.csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=["address", "global_idx", "pulses", "valid_three_2s"])
        wr.writeheader()
        for row in accel:
            wr.writerow({**row, "pulses": json.dumps(row["pulses"])})

    print(
        f"Wrote:\n  {op}.counts.csv\n  {op}.per_address.json\n  {op}.bit_edges.csv\n  {op}.candidates_window_only.csv\n  {op}.accel_hunt.csv"
    )


if __name__ == "__main__":
    main()
