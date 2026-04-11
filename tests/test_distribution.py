"""
Test suite for modules/distribution.py
"""

import pytest
from modules.distribution import (
    DistributionConfig,
    valider_distribution,
    get_required_formats,
    distribuer_track,
    VIDEO_FORMATS,
)


class TestDistributionConfig:
    """Tests pour DistributionConfig"""
    
    def test_from_dict_all_enabled(self):
        """Test création config avec toutes plateformes activées"""
        data = {
            "youtube": True,
            "youtube_short": True,
            "distrokid": True,
            "tiktok": True,
            "instagram_reels": True,
        }
        config = DistributionConfig.from_dict(data)
        assert config.youtube is True
        assert config.youtube_short is True
        assert config.distrokid is True
        assert config.tiktok is True
        assert config.instagram_reels is True
    
    def test_from_dict_partial(self):
        """Test création config avec certaines plateformes"""
        data = {"youtube": True, "tiktok": True}
        config = DistributionConfig.from_dict(data)
        assert config.youtube is True
        assert config.tiktok is True
        assert config.youtube_short is False
        assert config.distrokid is False
    
    def test_from_dict_none(self):
        """Test création config depuis None"""
        config = DistributionConfig.from_dict(None)
        assert not config.has_any()
    
    def test_has_any_true(self):
        """Test has_any retourne True si au moins une plateforme"""
        config = DistributionConfig(youtube=True)
        assert config.has_any()
    
    def test_has_any_false(self):
        """Test has_any retourne False si aucune plateforme"""
        config = DistributionConfig()
        assert not config.has_any()
    
    def test_platforms_enabled(self):
        """Test liste des plateformes activées"""
        config = DistributionConfig(
            youtube=True,
            youtube_short=True,
            tiktok=False,
        )
        platforms = config.platforms_enabled()
        assert "YouTube" in platforms
        assert "YouTube Short" in platforms
        assert "TikTok" not in platforms


class TestValiderDistribution:
    """Tests pour valider_distribution"""
    
    def test_valider_distribution_success(self):
        """Test validation réussie"""
        track = {
            "slug": "test-track",
            "distribution": {"youtube": True},
        }
        config = valider_distribution(track)
        assert config.youtube is True
    
    def test_valider_distribution_no_platforms(self):
        """Test erreur si aucune plateforme activée"""
        track = {
            "slug": "test-track",
            "distribution": {},
        }
        with pytest.raises(ValueError) as exc_info:
            valider_distribution(track)
        assert "aucune plateforme" in str(exc_info.value)
    
    def test_valider_distribution_youtube_short_missing_config(self):
        """Test erreur si youtube_short sans configuration video.short_clip"""
        track = {
            "slug": "test-track",
            "distribution": {"youtube_short": True},
            "video": {},
        }
        with pytest.raises(ValueError) as exc_info:
            valider_distribution(track)
        assert "short_clip" in str(exc_info.value)
    
    def test_valider_distribution_youtube_short_too_long(self):
        """Test erreur si youtube_short duration > 60s"""
        track = {
            "slug": "test-track",
            "distribution": {"youtube_short": True},
            "video": {
                "short_clip": {"duration_sec": 90}
            },
        }
        with pytest.raises(ValueError) as exc_info:
            valider_distribution(track)
        assert "60s" in str(exc_info.value)
    
    def test_valider_distribution_youtube_short_valid(self):
        """Test validation réussie pour youtube_short"""
        track = {
            "slug": "test-track",
            "distribution": {"youtube_short": True},
            "video": {
                "short_clip": {"duration_sec": 45}
            },
        }
        config = valider_distribution(track)
        assert config.youtube_short is True


class TestGetRequiredFormats:
    """Tests pour get_required_formats"""
    
    def test_get_required_formats_youtube_only(self):
        """Test formats requis pour YouTube seulement"""
        config = DistributionConfig(youtube=True)
        formats = get_required_formats(config)
        assert len(formats) == 1
        assert formats[0] == VIDEO_FORMATS['youtube']
    
    def test_get_required_formats_youtube_short(self):
        """Test formats requis pour YouTube Short"""
        config = DistributionConfig(youtube_short=True)
        formats = get_required_formats(config)
        assert len(formats) == 1
        assert formats[0] == VIDEO_FORMATS['youtube_short']
    
    def test_get_required_formats_both(self):
        """Test formats requis pour YouTube + YouTube Short"""
        config = DistributionConfig(youtube=True, youtube_short=True)
        formats = get_required_formats(config)
        assert len(formats) == 2
        assert VIDEO_FORMATS['youtube'] in formats
        assert VIDEO_FORMATS['youtube_short'] in formats
    
    def test_get_required_formats_social(self):
        """Test formats pour plateformes sociales"""
        config = DistributionConfig(
            youtube_short=True,
            tiktok=True,
            instagram_reels=True
        )
        formats = get_required_formats(config)
        # Un seul format vertical réutilisable
        assert len(formats) == 1
        assert formats[0].aspect_ratio == '9:16'


class TestDistribuerTrack:
    """Tests pour distribuer_track"""
    
    def test_distribuer_track_skip_upload(self, tmp_path):
        """Test distribution avec skip_upload"""
        track = {
            "slug": "test-track",
            "distribution": {"youtube": True},
        }
        results = distribuer_track(track, str(tmp_path), skip_upload=True)
        assert results["youtube"] is True
    
    def test_distribuer_track_invalid_config(self, tmp_path):
        """Test distribution avec config invalide lève ValueError"""
        track = {
            "slug": "test-track",
            "distribution": {},  # Aucune plateforme
        }
        with pytest.raises(ValueError):
            distribuer_track(track, str(tmp_path))
    
    def test_distribuer_track_multiple_platforms(self, tmp_path):
        """Test distribution multi-plateforme"""
        track = {
            "slug": "test-track",
            "distribution": {
                "youtube": True,
                "tiktok": True,
                "distrokid": True,
            },
        }
        results = distribuer_track(track, str(tmp_path), skip_upload=True)
        assert "youtube" in results
        assert "tiktok" in results
        assert "distrokid" in results
