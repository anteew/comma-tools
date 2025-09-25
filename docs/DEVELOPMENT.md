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
