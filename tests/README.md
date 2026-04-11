# Tests for Assirem Music Prod Pipeline

This directory contains pytest tests for the main modules.

## Running Tests

Install pytest if not already installed:
```bash
pip install pytest pytest-cov
```

Run all tests:
```bash
pytest
```

Run with coverage:
```bash
pytest --cov=modules --cov-report=html
```

Run specific test file:
```bash
pytest tests/test_http.py
pytest tests/test_distribution.py
```

Run with verbose output:
```bash
pytest -v
```

## Test Structure

- `conftest.py` - Pytest configuration and shared fixtures
- `test_http.py` - Tests for modules/_http.py utilities
- `test_distribution.py` - Tests for modules/distribution.py

## Adding New Tests

When adding new tests:
1. Create a new file `test_<module>.py`
2. Import the module to test
3. Use pytest fixtures from conftest.py
4. Follow the naming convention: `test_<function_name>_<scenario>()`

Example:
```python
def test_my_function_success(mock_track, mock_base_dir):
    result = my_function(mock_track, mock_base_dir)
    assert result == expected_value
```
