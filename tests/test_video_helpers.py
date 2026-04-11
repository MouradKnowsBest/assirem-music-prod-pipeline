"""
Tests des helpers purs de modules/video.py — pas de FFmpeg requis.
"""

import os
import tempfile

import pytest

from modules.video import (
    _slug_safe,
    _escape_concat,
    _escape_drawtext,
    _build_video_filter,
    _lister_mp3,
    _font_path,
)


# ─── _slug_safe ───────────────────────────────────────────────────────────────

class TestSlugSafe:
    def test_basic(self):
        assert _slug_safe("Hello World") == "hello_world"

    def test_special_chars(self):
        assert _slug_safe("Hello, World! 2026") == "hello_world_2026"

    def test_multiple_spaces(self):
        assert _slug_safe("a  b   c") == "a_b_c"

    def test_unicode(self):
        # Les emojis et caractères non-ASCII sont retirés par [^\w\s-]
        # \w inclut les lettres accentuées en Python 3
        result = _slug_safe("Été 2026 🌞")
        assert "été" in result or "t" in result  # dépend de la locale
        assert "🌞" not in result

    def test_empty(self):
        assert _slug_safe("") == ""

    def test_truncation(self):
        long = "a" * 200
        assert len(_slug_safe(long)) <= 80

    def test_leading_trailing_underscores(self):
        assert _slug_safe("---hello---") == "hello"

    def test_preserves_dashes(self):
        assert _slug_safe("afro-house-2026") == "afro_house_2026"


# ─── _escape_concat ───────────────────────────────────────────────────────────

class TestEscapeConcat:
    def test_no_apostrophe(self):
        assert _escape_concat("/tmp/file.mp3") == "/tmp/file.mp3"

    def test_with_apostrophe(self):
        # Format concat FFmpeg : ' → '\''
        assert _escape_concat("Don't.mp3") == "Don'\\''t.mp3"

    def test_multiple_apostrophes(self):
        assert _escape_concat("a'b'c") == "a'\\''b'\\''c"


# ─── _escape_drawtext ─────────────────────────────────────────────────────────

class TestEscapeDrawtext:
    def test_no_special(self):
        assert _escape_drawtext("Hello") == "Hello"

    def test_colon(self):
        assert _escape_drawtext("00:30") == "00\\:30"

    def test_backslash(self):
        assert _escape_drawtext("a\\b") == "a\\\\b"

    def test_apostrophe(self):
        assert _escape_drawtext("it's") == "it\\'s"

    def test_percent(self):
        assert _escape_drawtext("100%") == "100\\%"

    def test_combined(self):
        # Backslash échappé en premier, puis le reste
        assert _escape_drawtext("a:b%c") == "a\\:b\\%c"


# ─── _build_video_filter ──────────────────────────────────────────────────────

class TestBuildVideoFilter:
    def test_empty(self):
        """Aucun effet → chaîne vide."""
        assert _build_video_filter(duree=60, intro_fade=0, outro_fade=0) == ""

    def test_only_fade_in(self):
        result = _build_video_filter(duree=60, intro_fade=2, outro_fade=0)
        assert "fade=t=in:st=0:d=2" in result

    def test_only_fade_out(self):
        result = _build_video_filter(duree=60, intro_fade=0, outro_fade=3)
        assert "fade=t=out:st=57:d=3" in result

    def test_both_fades(self):
        result = _build_video_filter(duree=60, intro_fade=2, outro_fade=3)
        assert "fade=t=in" in result
        assert "fade=t=out" in result
        assert result.count(",") == 1  # deux filtres séparés par une virgule

    def test_outro_fade_longer_than_video(self):
        """Pas de fade-out si durée ≤ outro_fade (évite une valeur négative)."""
        result = _build_video_filter(duree=2, intro_fade=0, outro_fade=5)
        assert "fade=t=out" not in result

    def test_title_card_enabled(self):
        tc = {"enabled": True, "duration_sec": 3, "text": "Test Title", "subtitle": "Sub"}
        result = _build_video_filter(
            duree=60, intro_fade=0, outro_fade=0, title_card=tc
        )
        assert "drawtext" in result
        assert "Test Title" in result
        assert "Sub" in result
        assert "enable='lt(t,3" in result

    def test_title_card_disabled(self):
        tc = {"enabled": False, "text": "Should not appear"}
        result = _build_video_filter(
            duree=60, intro_fade=0, outro_fade=0, title_card=tc
        )
        assert "Should not appear" not in result

    def test_title_card_empty_text(self):
        """Pas de drawtext si text vide."""
        tc = {"enabled": True, "duration_sec": 3, "text": "", "subtitle": ""}
        result = _build_video_filter(
            duree=60, intro_fade=0, outro_fade=0, title_card=tc
        )
        assert "drawtext" not in result

    def test_end_card_with_subscribe_cta(self):
        ec = {"enabled": True, "duration_sec": 5, "subscribe_cta": True}
        result = _build_video_filter(
            duree=60, intro_fade=0, outro_fade=0, end_card=ec
        )
        assert "SUBSCRIBE" in result
        assert "enable='gt(t,55" in result  # duree - duration_sec

    def test_end_card_custom_text(self):
        ec = {"enabled": True, "duration_sec": 5, "text": "Thanks for watching"}
        result = _build_video_filter(
            duree=60, intro_fade=0, outro_fade=0, end_card=ec
        )
        assert "Thanks for watching" in result

    def test_all_effects_combined(self):
        tc = {"enabled": True, "duration_sec": 3, "text": "Title", "subtitle": ""}
        ec = {"enabled": True, "duration_sec": 5, "subscribe_cta": True}
        result = _build_video_filter(
            duree=60, intro_fade=2, outro_fade=3, title_card=tc, end_card=ec
        )
        assert "fade=t=in" in result
        assert "fade=t=out" in result
        assert "Title" in result
        assert "SUBSCRIBE" in result

    def test_escaping_in_title(self):
        """Les caractères spéciaux du titre doivent être échappés."""
        tc = {"enabled": True, "duration_sec": 3, "text": "It's 100%", "subtitle": ""}
        result = _build_video_filter(
            duree=60, intro_fade=0, outro_fade=0, title_card=tc
        )
        assert "\\'" in result  # apostrophe échappée
        assert "\\%" in result  # pourcent échappé


# ─── _lister_mp3 ──────────────────────────────────────────────────────────────

class TestListerMp3:
    def test_slug_dir_found(self, tmp_path):
        slug_dir = tmp_path / "lofi"
        slug_dir.mkdir()
        (slug_dir / "a.mp3").touch()
        (slug_dir / "b.mp3").touch()
        result = _lister_mp3(str(tmp_path), "lofi")
        assert len(result) == 2
        assert all(r.endswith(".mp3") for r in result)

    def test_fallback_to_input_root(self, tmp_path):
        (tmp_path / "song.mp3").touch()
        result = _lister_mp3(str(tmp_path), "non-existent-slug")
        assert len(result) == 1
        assert result[0].endswith("song.mp3")

    def test_no_mp3_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            _lister_mp3(str(tmp_path), "empty")

    def test_slug_dir_preferred_over_root(self, tmp_path):
        """Si input/<slug>/ a des mp3, on ignore ceux à la racine."""
        (tmp_path / "root.mp3").touch()
        slug_dir = tmp_path / "afrohouse"
        slug_dir.mkdir()
        (slug_dir / "slug.mp3").touch()
        result = _lister_mp3(str(tmp_path), "afrohouse")
        assert len(result) == 1
        assert "slug.mp3" in result[0]

    def test_sorted_output(self, tmp_path):
        slug_dir = tmp_path / "lofi"
        slug_dir.mkdir()
        (slug_dir / "c.mp3").touch()
        (slug_dir / "a.mp3").touch()
        (slug_dir / "b.mp3").touch()
        result = _lister_mp3(str(tmp_path), "lofi")
        assert [os.path.basename(r) for r in result] == ["a.mp3", "b.mp3", "c.mp3"]


# ─── _font_path ──────────────────────────────────────────────────────────────

class TestFontPath:
    def test_returns_string(self):
        """font_path doit toujours retourner une chaîne (même vide)."""
        result = _font_path()
        assert isinstance(result, str)

    def test_env_override(self, tmp_path, monkeypatch):
        fake_font = tmp_path / "fake.ttf"
        fake_font.touch()
        monkeypatch.setenv("ASSIREM_FONT", str(fake_font))
        assert _font_path() == str(fake_font)

    def test_env_override_missing_file(self, monkeypatch):
        """Si ASSIREM_FONT pointe vers un fichier inexistant, on ignore."""
        monkeypatch.setenv("ASSIREM_FONT", "/does/not/exist.ttf")
        result = _font_path()
        assert result != "/does/not/exist.ttf"
