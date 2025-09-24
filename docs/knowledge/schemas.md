# CSV Schema Reference (v1)

This document freezes the v1 schemas for all CSV exports produced by CruiseControlAnalyzer.

counts_by_segment.v1
Columns:
- address_hex
- bus
- pre_count
- window_count
- post_count
- delta
- uniq_pre
- uniq_window
- uniq_post

candidates.v1
Columns:
- address_hex
- bit_global
- byte_index
- bit_lsb
- bit_msb
- label_lsb
- label_msb
- score
- rises_set
- falls_end
- toggles
- penalty
- bus

edges.v1
Columns:
- address_hex
- bit_global
- byte_index
- bit_lsb
- bit_msb
- label_lsb
- label_msb
- ts_abs
- ts_rel
- ts_mmss
- edge
- speed_mph
- main
- brake
- bus

runs.v1
Columns:
- address_hex
- bit_global
- byte_index
- bit_lsb
- bit_msb
- label_lsb
- label_msb
- start_abs
- start_rel
- start_mmss
- end_abs
- end_rel
- end_mmss
- duration_s
- duration_mmss
- bus

timeline.v1
Columns:
- ts_abs
- ts_rel
- ts_mmss
- event_name
- description
- speed_mph

engaged_intervals.v1
Columns:
- address_hex
- bit_global
- byte_index
- bit_lsb
- bit_msb
- label_lsb
- label_msb
- start_abs
- start_rel
- start_mmss
- end_abs
- end_rel
- end_mmss
- duration_s
- duration_mmss
- bus

Conventions
- All CSV files include comment-prefixed metadata headers with a meta_json line.
- Time columns: single events use ts_abs/ts_rel/ts_mmss; intervals use start_*/end_* plus duration_s (3 decimals) and duration_mmss.
- Dual bit labeling: provide both LSB and MSB labels for bit positions.
- Deterministic sorting and numeric rounding are applied per artifact.

## How to Read CSV Headers

All exported CSV files include comment-prefixed metadata headers that provide essential context for analysis reproducibility and data interpretation.

### Header Structure

Each CSV begins with comment lines (starting with `#`) containing:

```csv
# schema_version: edges.v1
# analysis_id: 550e8400-e29b-41d4-a716-446655440000
# tool_version: a1b2c3d4 (git SHA)
# input_files: ["route_log.zst"]
# input_hashes: {"route_log.zst": "sha256:abc123..."}
# time_origin: 1640995200.0
# window_start_abs_s: 1640995260.5
# window_end_abs_s: 1640995290.8
# window_start_mmss: 01:00.500
# window_end_mmss: 01:30.800
# main_source: 0x119:MSB B2b3 (Steering_Torque)
# brake_source: 0x220:LSB B1b0 (Brake_Pressed)
# speed_source: 0x13A:computed (Wheel_Speeds_avg)
# id_bus_map: {"0x027":0,"0x119":0,"0x13A":0,"0x220":2,"0x321":2}
# bus_policy: first_seen
# engaged_mode: annotate
# engaged_bit: 0x027:MSB B5b1
# engaged_bus: 0
# engaged_margin_s: 0.5
# engaged_intervals_count: 3
# set_speed_min_mph: 55.0
# set_speed_max_mph: 56.0
# fall_window_s: 2.0
# chatter_penalty_start: 5
# chatter_penalty_slope: 0.1
# meta_json: {"schema_version":"edges.v1","analysis_id":"550e8400-e29b-41d4-a716-446655440000",...}
```

### Key Fields Explanation

**Analysis Identity**
- `analysis_id`: UUID for correlating related exports from same analysis run
- `tool_version`: Git SHA for reproducibility and version tracking
- `input_files`/`input_hashes`: Source data identification and integrity verification

**Time Context**
- `time_origin`: Absolute timestamp (Unix seconds) of log start
- `window_start/end_abs_s`: Analysis window boundaries in absolute time
- `window_start/end_mmss`: Human-readable time format (mm:ss.mmm)

**Signal Sources**
- `main_source`: Primary signal for analysis (e.g., steering torque)
- `brake_source`: Brake signal identification with bit specification
- `speed_source`: Speed calculation method and source address

**CAN Bus Configuration**
- `id_bus_map`: JSON mapping of CAN addresses to bus numbers
- `bus_policy`: Strategy for bus selection (first_seen, explicit, etc.)

**Engaged State Processing**
- `engaged_bit`: Bit selector for engaged intervals (e.g., "0x027:MSB B5b1")
- `engaged_mode`: Processing mode (annotate=include all, filter=engaged only)
- `engaged_margin_s`: Seconds to expand engaged intervals

**Analysis Parameters**
- `set_speed_min/max_mph`: Target speed range for event detection
- `fall_window_s`: Time window for analyzing signal transitions
- `chatter_penalty_*`: Scoring parameters for bit stability analysis

### Machine-Readable Metadata

The `meta_json` line contains the complete metadata as a JSON object for programmatic parsing:

```python
import json

# Parse CSV metadata
with open('edges.csv', 'r') as f:
    for line in f:
        if line.startswith('# meta_json:'):
            metadata = json.loads(line[13:])  # Skip "# meta_json: "
            break

print(f"Analysis ID: {metadata['analysis_id']}")
print(f"Window duration: {metadata['window_end_abs_s'] - metadata['window_start_abs_s']:.1f}s")
```

### Sidecar Files

Each CSV export also generates a corresponding `.analysis_meta.json` file with identical metadata for tools that prefer separate metadata files over CSV comments.
