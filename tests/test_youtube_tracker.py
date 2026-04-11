"""
Tests du tracker d'uploads YouTube journalier.
Ces fonctions sont pures (JSON sur disque), pas d'appel API.
"""

import json
import os
from datetime import date, timedelta
from unittest.mock import patch

import pytest

from modules.youtube import (
    _charger_tracker,
    _sauver_tracker,
    get_upload_count_today,
    _TRACKER_FILE,
)


class TestChargerTracker:
    def test_file_missing_returns_empty(self, tmp_path):
        tracker = _charger_tracker(str(tmp_path))
        assert tracker["uploads"] == 0
        assert tracker["slugs"] == []
        assert tracker["date"] == str(date.today())

    def test_file_from_today_is_loaded(self, tmp_path):
        path = tmp_path / _TRACKER_FILE
        data = {"date": str(date.today()), "uploads": 5, "slugs": ["lofi", "phonk"]}
        with open(path, "w") as f:
            json.dump(data, f)

        tracker = _charger_tracker(str(tmp_path))
        assert tracker["uploads"] == 5
        assert tracker["slugs"] == ["lofi", "phonk"]

    def test_file_from_yesterday_resets(self, tmp_path):
        """Changement de jour → compteur remis à zéro."""
        path = tmp_path / _TRACKER_FILE
        yesterday = str(date.today() - timedelta(days=1))
        data = {"date": yesterday, "uploads": 100, "slugs": ["old"]}
        with open(path, "w") as f:
            json.dump(data, f)

        tracker = _charger_tracker(str(tmp_path))
        assert tracker["uploads"] == 0
        assert tracker["slugs"] == []
        assert tracker["date"] == str(date.today())

    def test_corrupted_json_raises(self, tmp_path):
        """Un fichier JSON corrompu lève JSONDecodeError (comportement explicite)."""
        path = tmp_path / _TRACKER_FILE
        with open(path, "w") as f:
            f.write("not json{{{")

        with pytest.raises(json.JSONDecodeError):
            _charger_tracker(str(tmp_path))


class TestSauverTracker:
    def test_creates_file(self, tmp_path):
        tracker = {"date": str(date.today()), "uploads": 2, "slugs": ["a", "b"]}
        _sauver_tracker(str(tmp_path), tracker)

        path = tmp_path / _TRACKER_FILE
        assert path.exists()
        with open(path) as f:
            data = json.load(f)
        assert data == tracker

    def test_overwrites_existing(self, tmp_path):
        path = tmp_path / _TRACKER_FILE
        with open(path, "w") as f:
            json.dump({"date": "old", "uploads": 99, "slugs": []}, f)

        new = {"date": str(date.today()), "uploads": 1, "slugs": ["new"]}
        _sauver_tracker(str(tmp_path), new)

        with open(path) as f:
            data = json.load(f)
        assert data == new


class TestGetUploadCountToday:
    def test_missing_file_zero(self, tmp_path):
        nb, slugs = get_upload_count_today(str(tmp_path))
        assert nb == 0
        assert slugs == []

    def test_with_existing_uploads(self, tmp_path):
        data = {"date": str(date.today()), "uploads": 3, "slugs": ["a", "b", "c"]}
        with open(tmp_path / _TRACKER_FILE, "w") as f:
            json.dump(data, f)

        nb, slugs = get_upload_count_today(str(tmp_path))
        assert nb == 3
        assert slugs == ["a", "b", "c"]

    def test_round_trip(self, tmp_path):
        """Sauvegarder puis charger doit retourner les mêmes données."""
        initial = {"date": str(date.today()), "uploads": 7, "slugs": ["x"]}
        _sauver_tracker(str(tmp_path), initial)
        loaded = _charger_tracker(str(tmp_path))
        assert loaded["uploads"] == 7
        assert loaded["slugs"] == ["x"]
