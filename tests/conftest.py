"""
Configuration pytest pour les tests
"""

import pytest
import sys
import os

# Ajouter le répertoire parent au path pour importer les modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


@pytest.fixture
def mock_track():
    """Fixture pour un track de test standard"""
    return {
        "slug": "test-track-2026",
        "title": "Test Track",
        "description": "Description de test",
        "tags": ["test", "music"],
        "mode": "medium",
        "playlist_name": "Test Playlist",
        "distribution": {
            "youtube": True,
            "youtube_short": False,
        },
        "video": {
            "intro_fade_sec": 2,
            "outro_fade_sec": 3,
            "short_clip": {
                "start_sec": 10,
                "duration_sec": 55,
            }
        },
        "scenes": [
            {
                "prompt": "Test scene 1",
                "motion_strength": 3,
            },
            {
                "prompt": "Test scene 2",
                "motion_strength": 4,
            }
        ]
    }


@pytest.fixture
def mock_base_dir(tmp_path):
    """Fixture pour un répertoire de base de test"""
    # Créer structure minimale
    (tmp_path / "credentials").mkdir()
    (tmp_path / "input").mkdir()
    (tmp_path / "output").mkdir()
    return tmp_path
