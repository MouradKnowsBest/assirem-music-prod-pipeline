"""
Module distribution.py — Gestion de la distribution multi-plateforme

Centralise la logique de distribution pour YouTube, YouTube Shorts, 
TikTok, Instagram Reels, et DistroKid.

Chaque track dans config.json peut spécifier :
{
  "distribution": {
    "youtube": true,
    "youtube_short": true,
    "distrokid": true,
    "tiktok": true,
    "instagram_reels": true
  }
}

Ce module :
  - Valide la configuration de distribution
  - Génère les formats de vidéo appropriés (long, short, etc.)
  - Coordonne l'upload vers chaque plateforme
"""

import os
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class DistributionConfig:
    """Configuration de distribution pour un track"""
    youtube: bool = False
    youtube_short: bool = False
    distrokid: bool = False
    tiktok: bool = False
    instagram_reels: bool = False
    
    @classmethod
    def from_dict(cls, data: Optional[Dict]) -> 'DistributionConfig':
        """Crée une config depuis le dict du JSON"""
        if not data:
            return cls()
        return cls(
            youtube=data.get('youtube', False),
            youtube_short=data.get('youtube_short', False),
            distrokid=data.get('distrokid', False),
            tiktok=data.get('tiktok', False),
            instagram_reels=data.get('instagram_reels', False),
        )
    
    def has_any(self) -> bool:
        """Vérifie si au moins une plateforme est activée"""
        return any([
            self.youtube,
            self.youtube_short,
            self.distrokid,
            self.tiktok,
            self.instagram_reels,
        ])
    
    def platforms_enabled(self) -> List[str]:
        """Retourne la liste des plateformes activées"""
        platforms = []
        if self.youtube:
            platforms.append('YouTube')
        if self.youtube_short:
            platforms.append('YouTube Short')
        if self.distrokid:
            platforms.append('DistroKid')
        if self.tiktok:
            platforms.append('TikTok')
        if self.instagram_reels:
            platforms.append('Instagram Reels')
        return platforms


@dataclass
class VideoFormat:
    """Format de vidéo pour une plateforme"""
    name: str
    max_duration_sec: int
    aspect_ratio: str
    resolution: tuple  # (width, height)
    output_suffix: str  # ex: "_short", "_reel"


# Formats vidéo par plateforme
VIDEO_FORMATS = {
    'youtube': VideoFormat(
        name='YouTube Long',
        max_duration_sec=7200,  # 2h max
        aspect_ratio='16:9',
        resolution=(1920, 1080),
        output_suffix='',
    ),
    'youtube_short': VideoFormat(
        name='YouTube Short',
        max_duration_sec=60,
        aspect_ratio='9:16',
        resolution=(1080, 1920),
        output_suffix='_short',
    ),
    'tiktok': VideoFormat(
        name='TikTok',
        max_duration_sec=600,  # 10 min max
        aspect_ratio='9:16',
        resolution=(1080, 1920),
        output_suffix='_tiktok',
    ),
    'instagram_reels': VideoFormat(
        name='Instagram Reels',
        max_duration_sec=90,
        aspect_ratio='9:16',
        resolution=(1080, 1920),
        output_suffix='_reel',
    ),
}


def valider_distribution(track: dict) -> DistributionConfig:
    """
    Valide et retourne la configuration de distribution d'un track
    
    Args:
        track: Dict du track depuis config.json
    
    Returns:
        DistributionConfig validée
    
    Raises:
        ValueError: Si la config est invalide
    """
    config = DistributionConfig.from_dict(track.get('distribution'))
    
    if not config.has_any():
        raise ValueError(
            f"Track '{track.get('slug', '?')}' : "
            "aucune plateforme de distribution activée"
        )
    
    # Validation spécifique pour YouTube Short
    if config.youtube_short:
        video_config = track.get('video', {})
        short_config = video_config.get('short_clip')
        if not short_config:
            raise ValueError(
                f"Track '{track.get('slug', '?')}' : "
                "youtube_short activé mais video.short_clip non configuré"
            )
        duration = short_config.get('duration_sec', 0)
        if duration > 60:
            raise ValueError(
                f"Track '{track.get('slug', '?')}' : "
                f"YouTube Short duration_sec ({duration}s) dépasse 60s"
            )
    
    # Validation pour DistroKid (nécessite un MP3)
    if config.distrokid:
        # Vérifier qu'on a bien un fichier audio
        slug = track.get('slug', '')
        input_folder = track.get('input_folder', 'input')
        # Note: la validation complète sera faite au moment de l'upload
    
    return config


def get_required_formats(config: DistributionConfig) -> List[VideoFormat]:
    """
    Retourne la liste des formats vidéo à générer selon la config
    
    Args:
        config: Configuration de distribution
    
    Returns:
        Liste de VideoFormat requis
    """
    formats = []
    
    # Format long (16:9) pour YouTube et/ou DistroKid
    if config.youtube or config.distrokid:
        formats.append(VIDEO_FORMATS['youtube'])
    
    # Format vertical (9:16) pour YouTube Short, TikTok, Instagram Reels
    # On génère une seule vidéo verticale réutilisable
    if config.youtube_short or config.tiktok or config.instagram_reels:
        # Pour l'instant, on utilise le format YouTube Short comme base
        # qui peut être réutilisé pour TikTok et Instagram
        if config.youtube_short:
            formats.append(VIDEO_FORMATS['youtube_short'])
    
    return formats


def distribuer_track(track: dict, base_dir: str, skip_upload: bool = False) -> Dict[str, bool]:
    """
    Distribue un track sur toutes les plateformes configurées
    
    Args:
        track: Dict du track depuis config.json
        base_dir: Répertoire racine du projet
        skip_upload: Si True, génère les vidéos mais ne les upload pas
    
    Returns:
        Dict avec le statut de chaque plateforme {platform: success}
    
    Raises:
        ValueError: Si la configuration est invalide
    """
    config = valider_distribution(track)
    slug = track.get('slug', '?')
    
    print(f"\n  📤 Distribution : {', '.join(config.platforms_enabled())}")
    
    results = {}
    
    # YouTube
    if config.youtube:
        if skip_upload:
            print("  → YouTube : vidéo prête (upload sauté)")
            results['youtube'] = True
        else:
            # L'upload YouTube est géré par modules/youtube.py
            # Cette fonction sert surtout à coordonner
            results['youtube'] = None  # À implémenter
    
    # YouTube Short
    if config.youtube_short:
        if skip_upload:
            print("  → YouTube Short : vidéo prête (upload sauté)")
            results['youtube_short'] = True
        else:
            results['youtube_short'] = None  # À implémenter
    
    # DistroKid
    if config.distrokid:
        print("  → DistroKid : soumission manuelle requise")
        print(f"     Fichiers : output/{slug}/*.mp3 + output/{slug}/*_final.mp4")
        results['distrokid'] = None  # Distribution manuelle
    
    # TikTok
    if config.tiktok:
        if skip_upload:
            print("  → TikTok : vidéo prête (upload sauté)")
            results['tiktok'] = True
        else:
            print("  → TikTok : upload automatique non implémenté (manuel)")
            results['tiktok'] = None
    
    # Instagram Reels
    if config.instagram_reels:
        if skip_upload:
            print("  → Instagram Reels : vidéo prête (upload sauté)")
            results['instagram_reels'] = True
        else:
            print("  → Instagram Reels : upload automatique non implémenté (manuel)")
            results['instagram_reels'] = None
    
    return results
