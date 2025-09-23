# Subaru CXK Hybrid — Cruise/ACC Bit Hunting Kit (drop-in)

You've got two ready-to-run helpers:

1) **rlog_to_csv.py** — flatten an `rlog.zst` into a CSV your analyzers can chew.
2) **can_bitwatch.py** — find edges, candidates, and hunt the "three ~2s ACCEL pulses" across *all* bits.

## 1) rlog_to_csv.py

```
rlog-to-csv \
  --rlog /path/to/your.rlog.zst \
  --window-start 58918.188 \
  --window-dur 27.399 \
  --out window_1.csv \
  --repo-root /abs/path/to/openpilot   # optional if openpilot is alongside this folder
```

Columns: `window,segment,timestamp,address,bus,data_hex`  
- `segment`: pre / window / post  
- `timestamp`: seconds, relative to first CAN message.

## 2) can_bitwatch.py

```
can-bitwatch \
  --csv window_1.csv \
  --output-prefix analysis/window_1 \
  --watch 0x027:B4b5 0x027:B5b1 0x67A:B3b7 0x321:B5b1
```

Outputs:
- `analysis/window_1.counts.csv` — address × (pre, window, post, delta)
- `analysis/window_1.per_address.json` — per-address unique payload counts & top payloads
- `analysis/window_1.bit_edges.csv` — edge timeline for watched bits (with `mm:ss.mmm` relative to window start)
- `analysis/window_1.candidates_window_only.csv` — bits that toggle **only** inside the window
- `analysis/window_1.accel_hunt.csv` — looks for exactly **three** ~2.0 s pulses (±0.5 s) on any candidate bit

### Bit Labeling (your conventions baked in)

- **MSB-first** label `B4b5` → LSB bit = `2` → **global bit index** `34` (byte*8 + lsb).  
- We pack payload to little-endian u64: `int.from_bytes(payload, 'little')`.

### Defaults (tweakable with `--watch`)

- `0x027:B4b5`  (Cruise master ON — white icon; suspects gate)  
- `0x027:B5b1`  (watch alongside B4b5)  
- `0x67A:B3b7`  (strong engaged candidate from prior run)  
- `0x321:B5b1`  (CXK safety gate / engaged bit)

## Notes

- CSV can have `data_hex` formatted either `AABBCC...` or with spaces, both are accepted.
- If you omit `--window-start`, the analyzer infers it from the first `segment == window` row.
- The "ACCEL hunt" doesn't assume any specific ID — it tests **all bits** flagged as window-only togglers.
- For brake neighborhood triage, add an extra pass filtering addresses `0x139 0x138 0x13C 0x220 0x321` and cross-check edge times. (You can grep `bit_edges.csv` by those addresses.)

---

*Drop these into your repo (`comma-tools` or elsewhere) and go wild.*
