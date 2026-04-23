# Tests for Assirem Music Prod Pipeline

This directory contains pytest tests for `pipeline.py` and the `modules/` package.

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
pytest --cov=modules --cov=pipeline --cov-report=html
```

Run a specific test file:
```bash
pytest tests/test_distribution.py
pytest tests/test_pipeline_config.py
pytest tests/test_video_helpers.py
pytest tests/test_youtube_tracker.py
```

Run with verbose output:
```bash
pytest -v
```

## Test Structure

- `conftest.py` — Pytest configuration and shared fixtures
- `test_distribution.py` — Tests for `modules/distribution.py` (config multi-plateformes, validation, formats requis)
- `test_pipeline_config.py` — Tests du chargement de config et de la normalisation legacy dans `pipeline.py`
- `test_video_helpers.py` — Tests des helpers purs de `modules/video.py` (pas de FFmpeg requis)
- `test_youtube_tracker.py` — Tests du tracker d'uploads YouTube journalier (JSON sur disque, sans appel API)

## Adding New Tests

When adding new tests:
1. Create a new file `test_<module>.py`
2. Import the module to test
3. Use pytest fixtures from `conftest.py`
4. Follow the naming convention: `test_<function_name>_<scenario>()`

Example:
```python
def test_my_function_success(mock_track, mock_base_dir):
    result = my_function(mock_track, mock_base_dir)
    assert result == expected_value
```
