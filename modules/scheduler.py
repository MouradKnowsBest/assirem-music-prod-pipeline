"""
Smart scheduler — calcule publish_at optimal par track
en analysant channel_data.json + smart_schedule.json.
"""
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone

DAYS_EN = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
DAYS_FR = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']


def _analyze_channel_data(channel_data_path):
    """Retourne {(weekday_int, hour_utc): avg_views} depuis les analytics historiques."""
    if not os.path.exists(channel_data_path):
        return {}

    with open(channel_data_path) as f:
        data = json.load(f)

    by_slot = defaultdict(list)
    for v in data.get('videos', []):
        try:
            dt = datetime.fromisoformat(v['publishedAt'].replace('Z', '+00:00'))
            by_slot[(dt.weekday(), dt.hour)].append(v.get('viewCount', 0))
        except Exception:
            continue

    return {slot: sum(views) / len(views) for slot, views in by_slot.items()}


def _score_slot(dt_utc, category, analytics, schedule_config):
    """Score un créneau candidat pour une catégorie donnée."""
    categories = schedule_config.get('categories', {})
    cat_cfg = categories.get(category, categories.get('activity', {}))

    day = dt_utc.weekday()
    hour = dt_utc.hour

    # Score de base issu des analytics (défaut 30 si aucune donnée)
    base = analytics.get((day, hour), 30.0)

    boost = cat_cfg.get('boost', 1.0)

    # Bonus heure : rang dans preferred_hours_utc
    pref_hours = cat_cfg.get('preferred_hours_utc', [18])
    hour_rank = pref_hours.index(hour) if hour in pref_hours else len(pref_hours)
    hour_factor = max(0.5, 1.0 - hour_rank * 0.12)

    # Bonus jour : rang dans preferred_days
    pref_days = cat_cfg.get('preferred_days', [])
    day_name = DAYS_EN[day]
    if 'any' in pref_days:
        day_factor = 1.0
    elif day_name in pref_days:
        rank = pref_days.index(day_name)
        day_factor = max(0.5, 1.0 - rank * 0.08)
    else:
        day_factor = 0.4  # pénalité pour jour non préféré

    return base * boost * hour_factor * day_factor


def compute_schedule(tracks, base_dir, schedule_config_path=None):
    """
    Calcule publish_at optimal pour les tracks sans publish_at déjà défini.

    Retourne dict {slug: "YYYY-MM-DDTHH:MM:SS+00:00" | None}
    None = publication immédiate (aucun créneau disponible dans la fenêtre).
    """
    if schedule_config_path is None:
        schedule_config_path = os.path.join(base_dir, 'scripts', 'smart_schedule.json')

    if not os.path.exists(schedule_config_path):
        return {}

    with open(schedule_config_path) as f:
        schedule_cfg = json.load(f)

    channel_data_path = os.path.join(base_dir, 'scripts', 'channel_data.json')
    analytics = _analyze_channel_data(channel_data_path)

    rules = schedule_cfg.get('rules', {})
    min_gap_h    = rules.get('min_gap_hours', 2)
    max_per_day  = rules.get('max_videos_per_day', 3)
    window_days  = schedule_cfg.get('publish_window_days', 7)
    earliest_h   = rules.get('earliest_hour_utc', 8)
    latest_h     = rules.get('latest_hour_utc', 21)

    # Génère tous les créneaux candidats
    now_utc = datetime.now(timezone.utc)
    candidates = []
    for day_offset in range(window_days):
        for hour in range(earliest_h, latest_h + 1):
            base_day = (now_utc + timedelta(days=day_offset)).replace(
                hour=hour, minute=0, second=0, microsecond=0
            )
            if base_day > now_utc + timedelta(hours=1):
                candidates.append(base_day)
    candidates.sort()

    assigned        = []          # datetimes déjà assignés
    assigned_per_day = defaultdict(int)

    # Tracks déjà configurés avec publish_at → réserver leurs créneaux
    for track in tracks:
        pa = track.get('publish_at')
        if pa:
            try:
                dt = datetime.fromisoformat(pa.replace('Z', '+00:00'))
                assigned.append(dt)
                assigned_per_day[dt.date()] += 1
            except Exception:
                pass

    result = {}
    sorted_tracks = sorted(tracks, key=lambda t: t.get('priority', 99))

    for track in sorted_tracks:
        slug = track['slug']

        if track.get('publish_at'):
            result[slug] = track['publish_at']
            continue

        category = track.get('category', 'activity')
        cat_cfg  = schedule_cfg.get('categories', {}).get(category, {})

        # Épingler au jour de la fête si national_holiday
        holiday_date = None
        if cat_cfg.get('pin_to_event_date') and track.get('holiday_date'):
            try:
                holiday_date = datetime.fromisoformat(track['holiday_date']).date()
            except Exception:
                pass

        best_slot  = None
        best_score = -1.0

        for candidate in candidates:
            if holiday_date and candidate.date() != holiday_date:
                continue

            if assigned_per_day[candidate.date()] >= max_per_day:
                continue

            gap_ok = all(
                abs((candidate - a).total_seconds()) >= min_gap_h * 3600
                for a in assigned
            )
            if not gap_ok:
                continue

            score = _score_slot(candidate, category, analytics, schedule_cfg)
            if score > best_score:
                best_score = score
                best_slot  = candidate

        if best_slot:
            result[slug] = best_slot.strftime('%Y-%m-%dT%H:%M:%S+00:00')
            assigned.append(best_slot)
            assigned_per_day[best_slot.date()] += 1
        else:
            result[slug] = None

    return result


def format_schedule_summary(schedule_result, tracks, had_publish_at=None):
    """Retourne une liste de lignes lisibles pour affichage dans le pipeline."""
    if had_publish_at is None:
        had_publish_at = set()
    slug_to_track = {t['slug']: t for t in tracks}
    lines = []
    for slug, publish_at in schedule_result.items():
        track = slug_to_track.get(slug, {})
        cat   = track.get('category', '?')
        prio  = track.get('priority', '?')
        if publish_at:
            try:
                dt = datetime.fromisoformat(publish_at)
                day_fr = DAYS_FR[dt.weekday()]
                label = f"{day_fr} {dt.strftime('%d/%m à %H:%M')} UTC"
            except Exception:
                label = publish_at
        else:
            label = 'Immédiat'
        source = '(config)' if slug in had_publish_at else '(calculé)'
        lines.append(f"  [{prio}] {slug:<40} → {label}  {source}  [{cat}]")
    return lines
