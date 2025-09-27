# AI DEVELOPMENT STANDARDS & CONTRIBUTOR GUIDELINES

> **Note**: This repository maintains professional development standards. All AI contributors must follow these guidelines to ensure code quality, documentation excellence, and maintainable contributions.

## 🎯 CORE DEVELOPMENT PRINCIPLES

### Code Quality Standards
- **Type Hints Required**: All functions must include comprehensive type hints for parameters and return values
- **Docstring Excellence**: Use Google-style docstrings with detailed parameter descriptions, return values, and examples
- **Error Handling**: Document all exceptions that functions can raise, include proper error handling
- **Domain Expertise**: Leverage automotive/CAN bus knowledge - use hex addresses, understand vehicle systems
- **No Comments in Code**: Code should be self-documenting; avoid inline comments unless absolutely necessary

### Documentation Requirements
- **Sphinx Integration**: All new modules must be compatible with Sphinx autodoc
- **API Documentation**: Functions and classes must have complete docstrings that render beautifully in HTML
- **Examples Required**: Include practical usage examples in docstrings
- **Knowledge Base**: Complex concepts belong in the `knowledge/` directory with proper markdown documentation

### Testing & Verification Standards
- **Local Testing**: Always test changes locally before committing
- **CI Compliance**: All PRs must pass CI checks (build, test, lint)
- **Regression Testing**: Use the regression check procedures below before major changes
- **Real Data Validation**: When possible, test with actual vehicle logs and real-world scenarios

## 🏗️ REPOSITORY ARCHITECTURE

### Core Systems
- **Primary Tool**: `cruise_control_analyzer.py` - main analysis engine with self-contained dependency management
- **CAN Analysis**: Specialized decoders for Subaru and other vehicle platforms in `src/comma_tools/can/`
- **Monitoring Tools**: Real-time safety state monitoring in `src/comma_tools/monitors/`
- **Documentation**: Professional Sphinx-generated docs deployed to GitHub Pages

### Environment & Dependencies
- **Python Version**: Python 3.12 required (CI and tools only support 3.12)
- **Dependency Management**: Tools bootstrap their own environment, cache deps in `<repo-root>/comma-depends`
- **OpenPilot Integration**: Analyzer expects `openpilot/` alongside `comma-tools/`, override with `--repo-root`
- **Hardware Independence**: Tools stub hardware dependencies to work without comma devices

## 🚀 CONTRIBUTION WORKFLOW

### Branch & PR Standards
- **Branch Naming**: Use `devin/{timestamp}-{descriptive-slug}` format (generate timestamp with `date +%s`)
- **Commit Messages**: Descriptive, professional commit messages with bullet points for multiple changes
- **PR Requirements**: All PRs must include comprehensive descriptions, pass CI, and maintain documentation
- **Code Review**: PRs are automatically reviewed for adherence to these standards

### AI Agent Communication Protocol
**All AI contributors must use GitHub Issues for questions, discussions, and architectural guidance:**

- **New Conversations**: Create a new GitHub issue for net new topics, questions, or implementation discussions
- **Existing Discussions**: Continue conversations in existing issues rather than creating duplicates
- **Issue Naming**: Use descriptive titles like "Phase 4A Architectural Guidance: Error Handling Design Decisions"
- **Structured Questions**: Organize questions with clear headings, code examples, and specific architectural decisions needed
- **Cross-Reference**: Link related issues, PRs, and documentation for context
- **Professional Tone**: Maintain professional communication standards in all issue discussions

**Benefits of GitHub Issue Communication**:
- **Searchable History**: All architectural decisions and guidance are preserved and searchable
- **Team Visibility**: Other contributors can learn from discussions and avoid duplicate questions
- **Documentation Integration**: Issues serve as living documentation of design decisions
- **Accountability**: Clear record of who made what decisions and when

### Pre-Commit Checklist
1. **Install Pre-commit Hooks**: `pip install pre-commit && pre-commit install` (one-time setup)
2. **Run Pre-commit Checks**: `pre-commit run --all-files` (catches type/format errors locally)
3. **Manual Verification**: 
   - `mypy src/ --ignore-missing-imports` (type checking)
   - `black --check src/ tests/` (code formatting)
   - `flake8 src/ tests/ --count --select=E9,F63,F7,F82` (critical lint errors)
4. **Run Local Tests**: Verify all functionality works as expected
5. **Check Documentation**: Ensure Sphinx can build docs without errors (`sphinx-build -b html docs/ docs/_build/html`)
6. **Verify Type Hints**: All new functions have complete type annotations
7. **Update Dependencies**: If adding packages, update `pyproject.toml` and bootstrap requirements
8. **Test Real Scenarios**: Use actual log files when possible for validation

### Documentation Deployment
- **Automatic Deployment**: Docs auto-deploy to https://anteew.github.io/comma-tools/ on main branch merges
- **Local Preview**: Build docs locally to preview changes before committing
- **API Reference**: New modules automatically appear in API docs via Sphinx autodoc
- **Examples**: Include usage examples in both docstrings and `docs/examples.rst`
### Artifact Schemas (canonical, versioned)

- counts_by_segment.v1
  - Columns: address_hex, pre_count, window_count, post_count, uniq_pre, uniq_window, uniq_post, delta, bus
  - Sorting: delta desc, window_count desc, address_hex asc

- candidates.v1
  - Columns: address_hex, bit_global_lsb, bit_global_msb, score, rises_set, falls_end, penalty, bus
  - Sorting: score desc, address_hex asc, bit_global_lsb asc

- edges.v1
  - Columns: address_hex, bit_global_lsb, bit_global_msb, ts_abs, ts_rel, ts_str, edge_type, bus
  - Sorting: ts_abs asc, address_hex asc, bit_global_lsb asc

- runs.v1
  - Columns: address_hex, bit_global_lsb, bit_global_msb, start_ts_abs, start_ts_rel, start_ts_str, end_ts_abs, end_ts_rel, end_ts_str, duration_s, bus
  - Sorting: duration_s desc, address_hex asc, bit_global_lsb asc

- timeline.v1
  - Columns: ts_abs, ts_rel, ts_str, address_hex, bit_global_lsb, bit_global_msb, event, value, bus
  - Sorting: ts_abs asc, address_hex asc, event asc

Time fields:
- All time-bearing artifacts include absolute seconds (ts_abs), relative seconds (ts_rel) and mm:ss.mmm string (ts_str). Relative time origin defaults to window_start.

Bit labels:
- Dual representation is provided: bit_global_lsb and bit_global_msb. MSB index is computed as (width-1 - LSB).

CSV Header Metadata:
- Each CSV begins with a comment-prefixed metadata block including schema_version, analysis_id (UUIDv4), tool_version, input_files, input_hashes (sha256), time_origin, window_start/end (abs_s and mm:ss), gate sources (main_source, brake_source, speed_source), id_bus_map, bus_policy, scoring.
- A compact JSON copy is provided in `# meta_json: {...}` and duplicated in a sidecar `*.analysis_meta.json`.

Rounding:
- speed_mph rounded to 1 decimal; ts_rel and duration_s rounded to 3 decimals.

Change policy:
- Bump schema version on breaking changes (e.g., edges.v2). CI validates emitter column names against docs.


## 🔧 DEVELOPMENT ENVIRONMENT

### Quick Setup
```bash
# Clone and setup
git clone https://github.com/anteew/comma-tools.git
cd comma-tools
pip install -e ".[dev,docs]"

# Install pre-commit hooks (REQUIRED for development)
pip install pre-commit
pre-commit install

# Test documentation build
cd docs && sphinx-build -b html . _build/html

# Verify pre-commit setup
pre-commit run --all-files
```

### Pre-commit Workflow (MANDATORY)
The repository uses pre-commit hooks to catch mypy type errors, formatting issues, and security problems before they reach CI:

**Automatic Checks on Every Commit:**
- **mypy**: Type checking with `--ignore-missing-imports`
- **black**: Code formatting (line length 100)
- **flake8**: Critical syntax/undefined name errors
- **isort**: Import sorting
- **bandit**: Security vulnerability scanning
- **General**: Trailing whitespace, file endings, YAML/TOML validation

**Emergency Bypass (Use Sparingly):**
```bash
git commit --no-verify -m "emergency fix"  # Skips pre-commit hooks
```

**Local Verification Commands:**
```bash
# Run all pre-commit checks manually
pre-commit run --all-files

# Individual tool verification (matches CI exactly)
mypy src/ --ignore-missing-imports
black --check src/ tests/
flake8 src/ tests/ --count --select=E9,F63,F7,F82 --show-source --statistics
```

### Development Tools
- **Pre-commit Hooks**: Automated local checks for mypy, black, flake8, and security (prevents CI failures)
- **Sphinx Documentation**: Professional HTML docs with Furo theme
- **GitHub Actions**: Automated testing and deployment
- **Type Checking**: MyPy integration for type safety with strict Optional handling
- **Code Quality**: Automated linting and formatting checks (black, flake8, isort, bandit)

## 📋 RECENT ENHANCEMENTS
- **Professional Documentation**: Added Sphinx with GitHub Pages deployment and beautiful Furo theme
- **Comprehensive API Docs**: Auto-generated from excellent existing docstrings
- **Enhanced Analysis**: Blinker-based marker detection with configurable time windows
- **Robust Error Handling**: Immutable bytes conversion prevents pycapnp segfaults
- **Flexible Configuration**: CLI options for repo root, dependency directories, speed bounds

## 💡 DEVELOPMENT PRIORITIES
- **Real-World Testing**: Always validate with actual vehicle logs when possible
- **Cross-Platform Support**: Extend beyond Subaru to other vehicle platforms
- **Performance Optimization**: Consider caching parsed logs for repeated analysis
- **Enhanced Visualization**: Improve plotting and data presentation capabilities
- **Safety Integration**: Deeper integration with openpilot safety systems

## 🔍 TECHNICAL IMPLEMENTATION DETAILS

### Marker Window Analysis
- **Default Configuration**: Blinker-based markers (`--marker-type blinkers`)
- **Detection Logic**: Left-blinker ON → Right-blinker ON sequence within timeout window
- **Time Boundaries**: Configurable pre/post marker extensions (`--marker-pre`, `--marker-post`)
- **Activity Reporting**: Lists most active CAN addresses/bits during marker windows
- **Disable Option**: Use `--marker-type none` to disable marker-based windowing

### CAN Message Decoding
- **Subaru Specialization**: Primary focus on Subaru CAN protocols and addresses
- **Hex Address Usage**: Proper automotive convention (e.g., `0x119` for steering, `0x146` for cruise buttons)
- **Type Safety**: All CAN data converted to immutable bytes before processing
- **Error Resilience**: Graceful handling of malformed or missing CAN messages

## 🧪 REGRESSION TESTING PROTOCOL

### Complete End-to-End Validation
**Use this procedure before major changes or when validating new contributions:**

1. **Clean Environment Setup**:
   ```bash
   rm -rf ~/repos/comma-depends  # Optional: test fresh dependency installation
   cd ~/repos/comma-tools
   ```

2. **Primary Analysis Test**:
   ```bash
   python3 cruise_control_analyzer.py ../dcb4c2e18426be55_00000001--d6b09d8e76--0--rlog.zst --install-missing-deps
   ```
   **Expected Results**:
   - Dependency installation banner
   - "Openpilot modules loaded." message
   - Complete analysis report
   - Exit code `0`
   - Generated `speed_timeline.png` file

3. **Cached Dependencies Test**:
   ```bash
   python3 cruise_control_analyzer.py ../dcb4c2e18426be55_00000001--d6b09d8e76--0--rlog.zst
   ```
   **Expected Results**:
   - Skip pip installation step
   - Same successful analysis output

4. **Data Validation Checkpoints**:
   - "Extracted 6110 speed data points"
   - "Speed range: 1.0 - 22.6 MPH"
   - "No clear 'Set' button presses detected ..." (for this specific log)

**✅ Golden State**: All steps pass → Ready for development work
**❌ Failure**: Any step fails → Environment issue, investigate before proceeding

## 🎓 AI CONTRIBUTOR EXPECTATIONS

### Professional Standards
- **Domain Knowledge**: Understand automotive systems, CAN protocols, and openpilot architecture
- **Code Excellence**: Write production-quality code with comprehensive error handling
- **Documentation First**: Prioritize clear, comprehensive documentation over quick fixes
- **Testing Rigor**: Validate all changes with real-world data when possible
- **Collaborative Approach**: Respect existing patterns and architectural decisions

### Prohibited Actions
- **No Inline Comments**: Code should be self-documenting
- **No Breaking Changes**: Maintain backward compatibility unless explicitly required
- **No Shortcuts**: Follow all testing and documentation requirements
- **No Direct Main Commits**: Always use feature branches and PRs

---

*This repository represents professional-grade automotive debugging tools. Maintain these standards to ensure continued excellence and reliability for the openpilot community.*e.
