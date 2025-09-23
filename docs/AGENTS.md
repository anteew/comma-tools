# AGENTS NOTES

## Repository Structure
- `cruise_control_analyzer.py`: main tool for parsing rlog segments. Now bootstraps its own environment and caches third-party deps in `<repo-root>/comma-depends`.
- Other scripts are exploratory utilities for CAN analysis; see comments inside each script.

## Environment & Dependencies
- Requires Python 3.12 (CI and tools are only supported on Python 3.12).
- Analyzer auto-detects repo root (expects `openpilot/` alongside `comma-tools/`). Override with `--repo-root` if needed.
- Third-party packages installed locally: `matplotlib`, `numpy`, `pycapnp`, `tqdm`, `zstandard`, `pyzmq`, `smbus2`. Run once with `--install-missing-deps` to populate the cache.
- Analyzer stubs `openpilot.common.swaglog` to avoid hardware init; no comma device required.

## Recent Changes
- Added repo/dep bootstrap + CLI options (`--repo-root`, `--deps-dir`, `--install-missing-deps`).
- Added blinker-based marker detection with window analysis (`--marker-type/--marker-pre/--marker-post/--marker-timeout`).
- Converted stored CAN payloads to immutable `bytes` before analysis (prevents pycapnp buffer lifetime segfaults).
- `run_analysis` now accepts speed bounds; CLI passes `--speed-min/--speed-max` through.
- Verified analyzer on `dcb4c2e18426be55_00000001--d6b09d8e76--0--rlog.zst` (no cruise set button activity in that segment).

## How To Reproduce
1. `cd /home/dmann/repos/comma-tools`
2. `python3 cruise_control_analyzer.py ../<segment>.zst --install-missing-deps`
3. Re-run without `--install-missing-deps` afterwards. Plot saved as `speed_timeline.png`.

## Outstanding Ideas
- Integrate blinker-based markers to auto-window around cruise button presses.
- Expose raw CAN dump (+ unknown address highlighting) to assist manual inspection.
- Improve reporting when vehicle never hits target speed (currently notes zero events).
- Consider caching the parsed log output to speed up repeated analysis of same segment.

## Tips for Next Agent
- All edits so far are confined to `cruise_control_analyzer.py`; `git diff` shows context if further tweaks needed.
- Analyzer assumes Subaru-specific decoding; adjust `SubaruCANDecoder` if working on another platform.
- If openpilot schema moves, ensure `LogReader` import path still resolves through the submodule mirror (`openpilot/opendbc_repo/...`).
- When adding new dependencies, update the requirement list in `ensure_python_packages` to keep the bootstrap consistent.

## Marker Windows
- Default marker type is `'blinkers'`; use `--marker-type none` to disable.
- Script watches for left-blinker ON followed by right-blinker ON (within timeout) to define analysis windows.
- Window boundaries extend `--marker-pre` seconds before and `--marker-post` seconds after the markers.
- Reports list the most active CAN addresses/bits within each window (uses all recorded frames while markers are enabled).


## Quick Regression Check (Fresh Cache)
Use these steps whenever you need to prove the analyzer works end-to-end starting from an empty dependency cache.

1. Optional cleanup: remove the cached deps to mimic a clean environment.
   ```bash
   rm -rf ~/repos/comma-depends
   ```
2. Run the analyzer on a known-good log (the latest segment lives in `/home/dmann/` and a copy is in `/home/dmann/repos/`):
   ```bash
   cd ~/repos/comma-tools
   python3 cruise_control_analyzer.py ../dcb4c2e18426be55_00000001--d6b09d8e76--0--rlog.zst --install-missing-deps
   ```
   - Expect a dependency install banner followed by “Openpilot modules loaded.” and the full report.
   - Exit code should be `0` and `speed_timeline.png` appears in the working directory.
3. Re-run without the install flag to confirm cached imports work:
   ```bash
   python3 cruise_control_analyzer.py ../dcb4c2e18426be55_00000001--d6b09d8e76--0--rlog.zst
   ```
   - This should skip the pip step and still succeed.
4. (Optional) Spot-check critical stats in the report:
   - “Extracted 6110 speed data points”
   - “Speed range: 1.0 - 22.6 MPH”
   - “No clear 'Set' button presses detected …”

If all steps pass, you’re in the golden state and can begin modifying the analyzer with confidence.
