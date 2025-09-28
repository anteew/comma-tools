# Copilot Development Instructions

## Project Overview

This repository contains professional-grade automotive debugging and analysis tools for the openpilot autonomous driving system. The tools focus on Controller Area Network (CAN) bus analysis, safety system monitoring, and vehicle behavior debugging.

## Code Review Standards

When reviewing code, please be thorough and meticulous and really scrutinize the commits and PRs. The project manager is not a developer, and so you are entrusted to channel all of your GitHub expertise into keeping the code clean and pushing back on changes that don't make sense or insisting that commits and PRs are pristine.

It would be wonderful if you could also maintain a "map" of how the codebase works. Outside of testing or utilities that support project installation or setup, the primary logic should live in the service component and the front end code, whatever type it happens to be (cli, etc) should just be the front end...no application logic.

## Architecture Principles

### Service-First Architecture
- **Business Logic**: All primary logic must remain in analyzer classes under `src/comma_tools/analyzers/`
- **API Layer**: Keep FastAPI endpoints thin - they should only handle HTTP concerns, not duplicate business logic
- **CLI Layer**: Command-line interfaces should be pure frontend with no application logic
- **Separation of Concerns**: Service components handle logic, frontend handles user interaction

### Code Quality Standards
- **Type Hints Required**: All functions must include comprehensive type hints for parameters and return values
- **Docstring Excellence**: Use Google-style docstrings with detailed parameter descriptions, return values, and examples
- **Error Handling**: Document all exceptions that functions can raise, include proper error handling
- **Domain Expertise**: Leverage automotive/CAN bus knowledge - use hex addresses, understand vehicle systems
- **No Inline Comments**: Code should be self-documenting; avoid inline comments unless absolutely necessary

## Development Environment Requirements

### Pre-commit Workflow (MANDATORY)
The repository uses pre-commit hooks to catch issues before they reach CI:

**Automatic Checks on Every Commit:**
- **mypy**: Type checking with `--ignore-missing-imports`
- **black**: Code formatting (line length 100)
- **isort**: Import sorting
- **General**: Trailing whitespace, file endings, YAML/TOML validation

**Setup Commands:**
```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files  # Verify setup
```

**Local Verification Commands:**
```bash
# Run all pre-commit checks manually
pre-commit run --all-files

# Individual tool verification (matches CI exactly)
mypy src/ --ignore-missing-imports
black --check src/ tests/
```

### Testing Requirements
- **Python Version**: Python 3.12 required (CI and tools only support 3.12)
- **Local Testing**: Always test changes locally before committing
- **CI Compliance**: All PRs must pass CI checks (build, test, lint)
- **Real Data Validation**: When possible, test with actual vehicle logs and real-world scenarios
- **Integration Tests**: Use `--install-missing-deps` flags for tools that depend on openpilot

## Pull Request Requirements

1. **All CI checks must pass** (mypy, black, flake8, tests)
2. **Type annotations required** for new public APIs
3. **Documentation updates** for new features using Sphinx-compatible docstrings
4. **Test coverage** for new functionality
5. **Professional commit messages** with descriptive bullet points for multiple changes

### Code Review Checklist
- [ ] Type annotations are complete and accurate
- [ ] Optional dependencies handled properly with conditional imports
- [ ] Error handling includes proper types and documentation
- [ ] Tests cover new functionality
- [ ] Documentation updated if needed (Sphinx autodoc compatible)
- [ ] Pre-commit hooks pass locally
- [ ] Business logic stays in service components, not CLI/API layers
- [ ] Automotive domain knowledge applied correctly

## CI Troubleshooting for AI Contributors

### Critical CI Issue: Bootstrap Test Failures

**Common Failure**: GitHub Actions fails with `FileNotFoundError: Could not find the openpilot checkout` during integration tests.

**Root Cause**: The CI environment structure differs from local development:
```
# CI Structure (GitHub Actions)
$GITHUB_WORKSPACE/
├── comma-tools/    # Checked out with: path: comma-tools
└── openpilot/      # Checked out with: path: openpilot

# Local Development Structure  
parent-directory/
├── comma-tools/    # This repository
└── openpilot/      # Clone from commaai/openpilot
```

**Solution Pattern**: When writing integration tests or bootstrap code, always provide explicit workspace path for CI:

```python
# ❌ WRONG: Will fail in CI
from comma_tools.utils import find_repo_root
repo_root = find_repo_root()  # Can't find parent in CI

# ✅ CORRECT: Works in both local and CI environments
import os
from comma_tools.utils import find_repo_root
repo_root = find_repo_root(os.environ.get('GITHUB_WORKSPACE'))
```

**Workflow Pattern**: CI workflows should pass workspace explicitly:
```bash
# In .github/workflows/test.yml
python -c "
import os, sys
sys.path.insert(0, 'src')
from comma_tools.utils import find_repo_root
repo_root = find_repo_root(os.environ.get('GITHUB_WORKSPACE'))
# ... rest of bootstrap test
"
```

**Key Rules for AI Contributors**:
1. Never assume local development directory structure in CI tests
2. Always provide fallback environment detection for CI scenarios  
3. Use `$GITHUB_WORKSPACE` environment variable for CI workspace root
4. Test bootstrap code locally by simulating CI directory structure

## Domain-Specific Guidelines

### Automotive Systems Knowledge
- **CAN Protocol Understanding**: Work with hex addresses, understand bus topology
- **Vehicle Systems**: Brake systems, cruise control, safety monitoring
- **OpenPilot Integration**: Tools expect `openpilot/` alongside `comma-tools/`, override with `--repo-root`
- **Hardware Independence**: Tools stub hardware dependencies to work without comma devices

### Dependency Management
- **Bootstrap Environment**: Tools bootstrap their own environment, cache deps in `<repo-root>/comma-depends`
- **Optional Dependencies**: Handle gracefully with conditional imports and proper error messages
- **OpenPilot Compatibility**: Works with custom openpilot forks automatically

## Prohibited Actions
- **No Breaking Changes**: Maintain backward compatibility unless explicitly required
- **No Shortcuts**: Follow all testing and documentation requirements
- **No Direct Main Commits**: Always use feature branches and PRs
- **No Application Logic in CLI**: Keep command-line interfaces as pure frontend

## Additional Guidelines

### Documentation Standards
- **Sphinx Integration**: All new modules must be compatible with Sphinx autodoc
- **API Documentation**: Functions and classes must have complete docstrings that render beautifully in HTML
- **Examples Required**: Include practical usage examples in docstrings
- **Knowledge Base**: Complex concepts belong in the `knowledge/` directory with proper markdown documentation

### Branch & PR Standards
- **Branch Naming**: Use descriptive names that indicate the feature or fix
- **Commit Messages**: Professional, descriptive commit messages
- **PR Descriptions**: Comprehensive descriptions explaining the changes and their impact

## Additional Resources

For comprehensive development guidelines, see:
- `docs/AGENTS.md` - Complete AI development standards and contributor guidelines
- `docs/DEVELOPMENT.md` - Detailed development practices and workflow requirements
- `.pre-commit-config.yaml` - Pre-commit hook configuration

---

*This repository represents professional-grade automotive debugging tools. Maintain these standards to ensure continued excellence and reliability for the openpilot community.*
