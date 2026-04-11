"""
Tests du chargement de config et de la normalisation legacy dans pipeline.py.
"""

import json
import os
import sys

import pytest

# pipeline.py est à la racine → on l'importe comme module top-level
import pipeline as pipeline_mod


class TestNormaliserTrackLegacy:
    def test_defaults(self):
        """Un config vide donne des valeurs par défaut."""
        track = pipeline_mod._normaliser_track_legacy({})
        assert track["slug"] == "main"
        assert track["priority"] == 1
        assert track["mode"] == "medium"
        assert track["title"] == "Assirem Music"
        assert track["description"] == ""
        assert track["tags"] == []
        assert len(track["scenes"]) == 6  # nb_clips par défaut
        assert all("prompt" in s for s in track["scenes"])

    def test_custom_values(self):
        legacy = {
            "mode": "long",
            "title": "My Track",
            "description": "Desc",
            "tags": ["a", "b"],
            "playlist_name": "My Playlist",
            "leonardo_model": "custom-model-id",
            "visual_prompt": "sunset over mountains",
            "motion_strength": 8,
            "nb_clips": 4,
        }
        track = pipeline_mod._normaliser_track_legacy(legacy)
        assert track["mode"] == "long"
        assert track["title"] == "My Track"
        assert track["tags"] == ["a", "b"]
        assert track["playlist_name"] == "My Playlist"
        assert track["leonardo_model"] == "custom-model-id"
        assert len(track["scenes"]) == 4
        assert track["scenes"][0]["prompt"] == "sunset over mountains"
        assert track["scenes"][0]["motion_strength"] == 8

    def test_slug_always_main(self):
        """Le legacy normalise toujours vers slug='main'."""
        track = pipeline_mod._normaliser_track_legacy({"title": "Anything"})
        assert track["slug"] == "main"

    def test_default_input_folder(self):
        track = pipeline_mod._normaliser_track_legacy({})
        assert track["input_folder"] == "input"


class TestChargerTracks:
    def test_file_not_found(self, tmp_path):
        missing = str(tmp_path / "nope.json")
        with pytest.raises(FileNotFoundError):
            pipeline_mod.charger_tracks(missing)

    def test_multi_track_format(self, tmp_path):
        config = {
            "date": "2026-04-11",
            "priority_slug": "second",
            "tracks": [
                {"slug": "first", "priority": 2, "scenes": []},
                {"slug": "second", "priority": 1, "scenes": []},
            ],
        }
        path = tmp_path / "config.json"
        with open(path, "w") as f:
            json.dump(config, f)

        tracks, priority, source = pipeline_mod.charger_tracks(str(path))
        assert source == "config"
        assert len(tracks) == 2
        assert priority == "second"
        assert {t["slug"] for t in tracks} == {"first", "second"}

    def test_multi_track_default_priority(self, tmp_path):
        """Si priority_slug absent, utilise le premier track."""
        config = {
            "tracks": [
                {"slug": "alpha", "scenes": []},
                {"slug": "beta", "scenes": []},
            ],
        }
        path = tmp_path / "config.json"
        with open(path, "w") as f:
            json.dump(config, f)

        tracks, priority, source = pipeline_mod.charger_tracks(str(path))
        assert priority == "alpha"

    def test_legacy_single_track(self, tmp_path):
        """Un config sans `tracks` est normalisé en slug='main'."""
        config = {
            "mode": "medium",
            "title": "Legacy",
            "visual_prompt": "a prompt",
        }
        path = tmp_path / "config.json"
        with open(path, "w") as f:
            json.dump(config, f)

        tracks, priority, source = pipeline_mod.charger_tracks(str(path))
        assert source == "legacy"
        assert len(tracks) == 1
        assert tracks[0]["slug"] == "main"
        assert priority == "main"

    def test_empty_tracks_array(self, tmp_path):
        config = {"tracks": [], "priority_slug": ""}
        path = tmp_path / "config.json"
        with open(path, "w") as f:
            json.dump(config, f)

        tracks, priority, source = pipeline_mod.charger_tracks(str(path))
        assert tracks == []
        assert source == "config"
