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

### Pre-Commit Checklist
1. **Run Local Tests**: Verify all functionality works as expected
2. **Check Documentation**: Ensure Sphinx can build docs without errors (`sphinx-build -b html docs/ docs/_build/html`)
3. **Verify Type Hints**: All new functions have complete type annotations
4. **Update Dependencies**: If adding packages, update `pyproject.toml` and bootstrap requirements
5. **Test Real Scenarios**: Use actual log files when possible for validation

### Documentation Deployment
- **Automatic Deployment**: Docs auto-deploy to https://anteew.github.io/comma-tools/ on main branch merges
- **Local Preview**: Build docs locally to preview changes before committing
- **API Reference**: New modules automatically appear in API docs via Sphinx autodoc
- **Examples**: Include usage examples in both docstrings and `docs/examples.rst`

## 🔧 DEVELOPMENT ENVIRONMENT

### Quick Setup
```bash
# Clone and setup
git clone https://github.com/anteew/comma-tools.git
cd comma-tools
pip install -e ".[dev,docs]"

# Test documentation build
cd docs && sphinx-build -b html . _build/html
```

### Development Tools
- **Sphinx Documentation**: Professional HTML docs with Furo theme
- **GitHub Actions**: Automated testing and deployment
- **Type Checking**: MyPy integration for type safety
- **Code Quality**: Automated linting and formatting checks

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
