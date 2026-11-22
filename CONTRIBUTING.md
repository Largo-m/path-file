# Contributing to path_file

Thank you for your interest in contributing to path_file! This document provides guidelines for contributing.

## Quick Start

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/path_file.git`
3. Create a virtual environment: `python -m venv venv && source venv/bin/activate`
4. Install in development mode: `pip install -e ".[dev]"`
5. Install pre-commit hooks: `pre-commit install`
6. Run tests: `pytest`

## Development Setup

```bash
# Clone
git clone https://github.com/Largo-m/path-file.git
cd path_file

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run tests
pytest

# Run linting
ruff check src tests
mypy src

# Format code
ruff format src tests
```

## Code Style

- **Formatter**: Ruff (compatible with Black)
- **Linter**: Ruff
- **Type Checker**: mypy (strict mode)
- **Line Length**: 100 characters
- **Python Version**: 3.10+

### Type Hints

All public APIs must have complete type hints:

```python
def function(param: Type) -> ReturnType:
    """Docstring with example."""
    ...
```

No `Any` in public APIs. Use precise types.

### Docstrings

All public functions, classes, and methods must have docstrings:

```python
def find_files(path: Path, pattern: str) -> List[Path]:
    """
    Find files matching pattern.
    
    Args:
        path: Directory to search
        pattern: Glob pattern
    
    Returns:
        List of matching file paths
    
    Example:
        >>> find_files(Path("~/Downloads"), "*.jpg")
        [PosixPath('~/Downloads/photo.jpg')]
    """
```

## Testing

- Write tests for new features
- Maintain 85%+ coverage
- Test edge cases and error conditions
- Use fixtures from `conftest.py`

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=path_file --cov-report=html

# Run specific test file
pytest tests/test_chain.py

# Run with verbose output
pytest -v
```

## Pull Request Process

1. Create a feature branch: `git checkout -b feature/amazing-feature`
2. Make your changes
3. Run tests and linting: `pytest && ruff check src tests && mypy src`
4. Commit with conventional commits: `git commit -m "feat: add amazing feature"`
5. Push to your fork: `git push origin feature/amazing-feature`
6. Open a Pull Request

### Commit Message Format

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Formatting, missing semicolons, etc.
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `perf`: Performance improvement
- `test`: Adding missing tests
- `chore`: Maintenance tasks

Examples:
```
feat(chain): add .duplicates_by_name() filter
fix(archive): handle path traversal in tar extraction
docs(readme): add quickstart example
test(filters): add test for filter_between_sizes
```

## Reporting Bugs

Use the bug report template when filing issues. Include:

- Python version
- OS
- path_file version
- Minimal reproduction code
- Expected vs actual behavior
- Full traceback if applicable

## Suggesting Features

Use the feature request template. Explain:

- The problem you're trying to solve
- Your proposed solution
- Alternatives considered
- Any implementation ideas

## Code of Conduct

Please read and follow our [Code of Conduct](CODE_OF_CONDUCT.md).

## License

By contributing, you agree that your contributions will be licensed under the MIT License.