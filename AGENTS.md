## Python Environment Management

This project uses [`uv`](https://docs.astral.sh/uv/) for all Python environment
management, dependency handling, and tool execution.
Always use `uv` instead of direct `python`, `pip`, or `pipx` commands:

## Code Quality Checks

After every code change, you MUST run the following quality checks:

### 1. Ruff Linting

Check code for linting errors:

```bash
uv run ruff check --fix .
```

### 2. Ruff Formatting

Format code automatically:

```bash
uv run ruff format .
```

### 3. Type Checking with ty

Run type checking:

```bash
uv run ty check
```

## Coding/Formatting Guidelines

### Function Signatures

All methods should enforce keyword-only arguments using the `*` operator:

```python
def my_function(*, arg1: str, arg2: int) -> None:
    ...
```

### Type Annotations

Everything should be typed. All functions, methods, and variables must have explicit
type annotations.

### Docstrings

Docstrings should be used only when needed. Avoid redundant documentation for
self-explanatory code.

## Testing

All features should be tested by textual builtin testing framework and pytest