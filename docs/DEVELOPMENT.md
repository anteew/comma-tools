# Development Guide

This guide covers development practices, code quality standards, and workflow requirements for the comma-tools repository.

## Quick Start

1. **Install development dependencies:**
   ```bash
   pip install -e ".[dev]"
   ```

2. **Install pre-commit hooks:**
   ```bash
   pip install pre-commit
   pre-commit install
   ```

3. **Run pre-commit on all files (optional):**
   ```bash
   pre-commit run --all-files
   ```

## Code Quality Standards

### Type Checking with mypy

All code must pass mypy type checking. Common patterns to follow:

#### Optional Parameters
```python
# ✅ GOOD: Proper Optional typing
def command_function(
    param: str,
    http_client: Optional[HTTPClient] = None,
    renderer: Optional[Renderer] = None,
) -> int:
    if http_client is None or renderer is None:
        raise ValueError("http_client and renderer are required")
```

#### JSON Response Handling
```python
# ✅ GOOD: Proper type handling for API responses
def handle_api_response(response_data: List[Dict[str, Any]]) -> None:
    for item in response_data:
        # item is Dict[str, Any], safe to use .get()
        item_id = item.get("id", "")
        status = item.get("status", "unknown")
```

#### Optional Rich Dependencies
```python
# ✅ GOOD: Conditional imports with type safety
try:
    from rich.console import Console
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

class Renderer:
    def __init__(self, json_output: bool = False):
        self.console: Optional[object] = None
        if RICH_AVAILABLE and not json_output:
            from rich.console import Console
            self.console = Console()
    
    def print_message(self, message: str) -> None:
        if self.console:
            self.console.print(message)  # type: ignore
        else:
            print(message)
```

### Common Type Error Patterns to Avoid

1. **Non-optional parameters with None defaults:**
   ```python
   # ❌ BAD
   def func(client: HTTPClient = None):  # mypy error
   
   # ✅ GOOD
   def func(client: Optional[HTTPClient] = None):
   ```

2. **Incorrect JSON shape assumptions:**
   ```python
   # ❌ BAD: Assuming response is directly iterable as dicts
   for item in http_client.get_json("/endpoint"):
       item.get("field")  # mypy error: str has no attribute 'get'
   
   # ✅ GOOD: Proper type handling
   response: List[Dict[str, Any]] = http_client.get_json("/endpoint")
   for item in response:
       item.get("field")  # OK
   ```

3. **Module fallback imports:**
   ```python
   # ❌ BAD: Reassigning module name to None
   try:
       import tomllib
   except ImportError:
       tomllib = None  # mypy error: redefinition
   
   # ✅ GOOD: Use different variable or type: ignore
   try:
       import tomllib
   except ImportError:
       tomllib = None  # type: ignore
   ```

## Pre-commit Hooks

The repository uses pre-commit hooks to catch issues before they reach CI:

- **black**: Code formatting (line length 100)
- **isort**: Import sorting
- **flake8**: Basic linting (syntax errors, undefined names)
- **mypy**: Type checking
- **bandit**: Security checks
- **General**: Trailing whitespace, file endings, YAML/TOML validation

### Running Checks Locally

Before committing, run these commands to match CI requirements:

```bash
# Type checking (matches CI)
mypy src/ --ignore-missing-imports

# Code formatting (matches CI)
black --check src/ tests/

# Linting (matches CI)
flake8 src/ tests/ --count --select=E9,F63,F7,F82 --show-source --statistics

# Run all pre-commit hooks
pre-commit run --all-files
```

### Bypassing Pre-commit (Emergency Only)

In rare cases where you need to commit without running hooks:
```bash
git commit --no-verify -m "emergency fix"
```

**Note:** This should only be used for critical hotfixes. The CI will still enforce all checks.

## Testing Guidelines

### Type Safety in Tests

1. **Mock objects should have proper types:**
   ```python
   from unittest.mock import Mock
   
   # ✅ GOOD: Typed mock
   mock_client = Mock(spec=HTTPClient)
   mock_client.get_json.return_value = {"status": "ok"}
   ```

2. **Test data should match expected types:**
   ```python
   # ✅ GOOD: Proper test data structure
   test_response: List[Dict[str, Any]] = [
       {"id": "123", "status": "completed"},
       {"id": "456", "status": "running"},
   ]
   ```

### Integration Tests

For tools that depend on external repositories (like openpilot):
- Use `--install-missing-deps` flags in tests
- CI checks out dependencies side-by-side
- Test on Python 3.12 only (openpilot requirement)

## CI Workflow

The repository has two CI jobs:

1. **test-core**: Core functionality without visualization dependencies
2. **test-visualization**: Full testing with mypy, black, flake8, and visualization

### CI Failure Debugging

If CI fails on type checking:

1. **Run mypy locally first:**
   ```bash
   mypy src/ --ignore-missing-imports
   ```

2. **Check for common patterns:**
   - Optional parameter typing
   - JSON response handling
   - Conditional import patterns

3. **Fix locally and verify:**
   ```bash
   # Fix issues, then verify
   mypy src/ --ignore-missing-imports
   black --check src/ tests/
   flake8 src/ tests/ --count --select=E9,F63,F7,F82
   ```

## Contributing Guidelines

### Pull Request Requirements

1. **All CI checks must pass** (mypy, black, flake8, tests)
2. **Type annotations required** for new public APIs
3. **Documentation updates** for new features
4. **Test coverage** for new functionality

### Code Review Checklist

- [ ] Type annotations are complete and accurate
- [ ] Optional dependencies handled properly
- [ ] Error handling includes proper types
- [ ] Tests cover new functionality
- [ ] Documentation updated if needed
- [ ] Pre-commit hooks pass locally

### AI Contributor Guidelines

When working on this codebase:

1. **Always run verification steps** before committing
2. **Use proper type annotations** from the start
3. **Handle optional dependencies** with conditional imports
4. **Test locally** before pushing to CI
5. **Follow existing patterns** for similar functionality

## Dependency Management

### Core Dependencies
- Required for all installations
- Listed in `dependencies` section of pyproject.toml

### Optional Dependencies
- `[plot]`: Matplotlib for visualization
- `[connect]`: comma.ai API integration
- `[client]`: CTS CLI client dependencies
- `[dev]`: All development tools (mypy, black, flake8, etc.)

### Adding New Dependencies

1. **Determine the right category** (core vs optional)
2. **Add to appropriate section** in pyproject.toml
3. **Update CI if needed** (test-core vs test-visualization)
4. **Use lazy imports** for optional dependencies

## Architecture Guidelines

### Type Safety Patterns

1. **Use Protocol classes** for interface definitions
2. **Prefer composition** over inheritance for testability
3. **Handle None values explicitly** with Optional types
4. **Use TypedDict** for structured data when appropriate

### API Version Compatibility

The CTS-Lite API implements version compatibility checking:

**Server Side** (`src/comma_tools/api/version.py`):
```python
# When making breaking API changes, update these constants
API_VERSION = "0.1.0"          # Current API version
MIN_CLIENT_VERSION = "0.8.0"   # Minimum required client version
```

**Client Side** (`src/cts_cli/main.py`):
- Automatically checks `/v1/version` on startup
- Compares client version with server's `min_client_version`
- Shows clear error if client is too old
- Silently continues if endpoint doesn't exist (backward compatibility)

**When to Update Versions**:
1. **Breaking API changes**: Increment `MIN_CLIENT_VERSION` in `version.py`
2. **New API features**: Increment `API_VERSION`, keep `MIN_CLIENT_VERSION` unchanged
3. **Client updates**: Keep `__version__` in `src/cts_cli/__init__.py` in sync with project version

**Testing Version Compatibility**:
```python
# Test with mismatched versions
def test_version_incompatibility():
    # Start server with MIN_CLIENT_VERSION = "2.0.0"
    # Run client with version "0.8.0"
    # Verify client shows upgrade error
```

### MCP Server Development

The comma-tools MCP (Model Context Protocol) server enables AI assistants to programmatically access the CTS-Lite API. This section covers development and testing for developers working on the MCP server itself.

> **Note**: This section is for developers working on the MCP server. If you are an AI assistant wanting to use the MCP server, see [src/comma_tools_mcp/README.md](../src/comma_tools_mcp/README.md) instead.

**Installation**:
```bash
pip install -e ".[mcp]"
```

**Architecture**:
- **Location**: `src/comma_tools_mcp/`
- **Framework**: FastMCP (MCP Python SDK)
- **Transport**: stdio (standard input/output)
- **Entry Point**: `cts-mcp` command
- **Communication**: MCP server ↔ CTS-Lite API (HTTP)

**Available Tools** (10 total):
- Health & Discovery: `check_health()`, `get_version()`, `list_capabilities()`
- Analysis: `run_analysis()`, `get_run_status()`, `list_runs()`
- Artifacts: `list_artifacts()`, `get_artifact_content()`, `download_artifact()`

**Available Resources** (2 total):
- `cts://config` - Server configuration
- `cts://capabilities` - Available tools summary

**Adding New Tools**:
```python
from mcp import types

@mcp.tool()
def my_new_tool(param: str) -> Dict[str, Any]:
    """
    Description for AI assistants to understand when to use this tool.

    Args:
        param: Parameter description

    Returns:
        Return value description
    """
    return make_request("GET", f"/v1/my-endpoint/{param}")
```

**Testing the MCP Server**:

1. **Start CTS-Lite API**:
   ```bash
   cts-lite &
   ```

2. **Test tools directly** (Python):
   ```bash
   python test_mcp_workflow.py
   ```

3. **Test with MCP Inspector** (interactive):
   ```bash
   pip install mcp-inspector
   mcp dev src/comma_tools_mcp/server.py
   ```

4. **Test AI registration** (Claude Code):
   ```bash
   # Find cts-mcp command
   find . -name cts-mcp -path "*/venv/bin/*" | head -1

   # Register to Claude Code
   claude mcp add comma-tools --scope user \
     -e CTS_LITE_URL=http://127.0.0.1:8080 \
     -- /path/to/venv/bin/cts-mcp

   # Verify
   claude mcp list
   ```

**Type Safety for MCP Tools**:
```python
# ✅ GOOD: Proper typing for MCP tool functions
from typing import Dict, Any, Optional, List

@mcp.tool()
def typed_tool(
    required_param: str,
    optional_param: Optional[int] = None,
) -> Dict[str, Any]:
    """Tool with proper type hints."""
    payload: Dict[str, Any] = {"param": required_param}
    if optional_param is not None:
        payload["optional"] = optional_param
    return make_request("POST", "/v1/endpoint", json=payload)
```

**Common MCP Development Patterns**:

1. **Always test with CTS-Lite running**: MCP server proxies to API
2. **Use `make_request()` helper**: Handles HTTP client, error handling, base URL
3. **Match API payload format**: Check `src/comma_tools/api/models.py` for exact schemas
4. **Provide clear tool descriptions**: AI assistants use docstrings to understand when to call tools
5. **Return structured data**: Always return `Dict[str, Any]` for JSON-serializable responses

**Debugging Tips**:

- **MCP Inspector**: Best for interactive testing of individual tools
- **test_mcp_workflow.py**: End-to-end validation of full workflow
- **Logs**: MCP server logs to stderr, CTS-Lite logs to stdout
- **API Docs**: Check `/docs` endpoint on CTS-Lite for API schema

**Documentation Locations**:
- **Developer docs**: This file (DEVELOPMENT.md)
- **AI usage docs**: `src/comma_tools_mcp/README.md` (self-registration instructions)
- **Human usage docs**: `README.md` (clarifies MCP is for AIs)
- **Agent docs**: `docs/AGENTS.md` (AI contributor guidelines)

### Error Handling

```python
# ✅ GOOD: Proper error handling with types
def safe_api_call(client: HTTPClient, endpoint: str) -> Optional[Dict[str, Any]]:
    try:
        response = client.get_json(endpoint)
        return response
    except (HTTPError, ConnectionError) as e:
        logger.error(f"API call failed: {e}")
        return None
```

## Troubleshooting

### Common mypy Issues

1. **"Incompatible default for argument"**
   - Add `Optional[]` type annotation
   - Check for None defaults with non-optional types

2. **"has no attribute"**
   - Check JSON response handling
   - Verify object types before attribute access

3. **"Cannot assign to a type"**
   - Usually from conditional imports
   - Use `# type: ignore` for fallback assignments

### Performance Considerations

- **Lazy imports** for optional dependencies
- **Type checking overhead** is minimal at runtime
- **Pre-commit hooks** add ~10-30 seconds to commit time
- **CI type checking** prevents longer debugging cycles

## Resources

- [mypy documentation](https://mypy.readthedocs.io/)
- [black code style](https://black.readthedocs.io/)
- [pre-commit hooks](https://pre-commit.com/)
- [Python typing guide](https://docs.python.org/3/library/typing.html)
