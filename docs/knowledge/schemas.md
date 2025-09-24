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
