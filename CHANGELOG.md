# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.8.0] - 2024-09-24

### Added - Exports/Reporting v1
- **CSV Export System**: Complete CSV export functionality with versioned schemas (v1)
  - `counts_by_segment.csv` - CAN address activity analysis with pre/window/post segmentation
  - `candidates.csv` - Bit-level analysis with scoring and penalty calculations
  - `edges.csv` - Bit transition events with timing and speed correlation
  - `runs.csv` - Duration-based interval analysis with start/end timestamps
  - `timeline.csv` - Chronological event timeline with speed correlation
  - `engaged_intervals.csv` - Engaged state bracketing with configurable margins
- **JSON Export System**: Parallel JSON exports for all CSV data with identical schemas
- **HTML Report Generation**: Professional analysis reports with embedded CSS styling
- **Metadata Headers**: Comment-prefixed CSV headers with schema versioning and analysis metadata
- **Dual Bit Labeling**: Both LSB and MSB bit position formats for automotive compatibility
- **Time Format Standardization**: Absolute seconds, relative seconds, and mm:ss.mmm formats
- **Engaged Interval Processing**: Configurable filtering and annotation modes
- **Configuration Snapshots**: Complete analysis parameter capture in JSON format

### Enhanced
- **CLI Interface**: Added `--export-csv`, `--export-json`, `--output-dir` options
- **Engaged Analysis**: Added `--engaged-bit`, `--engaged-bus`, `--engaged-mode`, `--engaged-margin` options
- **Schema Validation**: Deterministic sorting and numeric rounding for reproducible outputs
- **Error Handling**: Graceful handling of empty results with proper CSV headers

### Technical
- **Schema Versioning**: Frozen v1 schemas for all export formats
- **Metadata Standards**: UUID analysis IDs, SHA256 input hashing, git version tracking
- **Bus Policy Recording**: Complete CAN bus selection and routing documentation
- **Gate Source Tracking**: Main/brake/speed source configuration preservation

## [0.1.0] - 2024-12-20

### Added
- Initial release with core cruise control analysis functionality
- Subaru CAN message decoding and analysis
- Marker-based time window detection
- Speed timeline visualization
- Real-time safety monitoring tools
