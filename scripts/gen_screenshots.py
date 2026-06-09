"""
Génère tous les screenshots PNG pour le dossier de conformité YouTube API.
Produit dans: scripts/compliance_screenshots/

Screenshots générés (style code editor + terminal dark) :
  B  config_metadata.png       — extrait config.json avec métadonnées
  C  code_videos_insert.png    — videos.insert() dans youtube.py
  D  code_thumbnails_set.png   — thumbnails.set() dans youtube.py
  E  code_playlist_insert.png  — playlistItems.insert() dans youtube.py
  F  code_authentifier.png     — _authentifier() dans youtube.py
  G  terminal_token_loaded.png — sortie terminal : token OAuth2 chargé
  H  terminal_upload_full.png  — sortie terminal : upload complet

Usage:
  python scripts/gen_screenshots.py
"""

import os
import sys
import json
import textwrap

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "compliance_screenshots")
os.makedirs(OUT_DIR, exist_ok=True)

# ── Pillow setup ──────────────────────────────────────────────────────────────
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Pillow requis : pip install pillow")
    sys.exit(1)

W = 1200

# ── Fonts ─────────────────────────────────────────────────────────────────────
def _mono(size):
    for p in [
        "/System/Library/Fonts/Menlo.ttc",
        "/System/Library/Fonts/Monaco.ttf",
        "/Library/Fonts/Courier New.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ]:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, size)
            except: pass
    return ImageFont.load_default()

def _sans(size):
    for p in [
        "/System/Library/Fonts/Supplemental/Futura.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
    ]:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, size)
            except: pass
    return ImageFont.load_default()


# ── Color schemes ─────────────────────────────────────────────────────────────
# VS Code Dark+ inspired
BG       = (30, 30, 30)
BG_TAB   = (37, 37, 38)
GUTTER   = (50, 50, 50)
LINE_NUM = (133, 133, 133)
TEXT     = (212, 212, 212)
KW       = (86, 156, 214)    # blue — keywords
STR      = (206, 145, 120)   # orange — strings
COMMENT  = (106, 153, 85)    # green — comments
FUNC     = (220, 220, 170)   # yellow — function names
PUNCT    = (180, 180, 180)   # punctuation

# Terminal
TERM_BG   = (13, 17, 23)
TERM_TEXT = (201, 209, 217)
TERM_BLUE = (88, 166, 255)
TERM_GREEN= (63, 185, 80)
TERM_GREY = (139, 148, 158)
TERM_YELL = (210, 153, 34)
TERM_PROM = (248, 94, 61)


# ── Core rendering ────────────────────────────────────────────────────────────

def _line_height(font, draw, text="A") -> int:
    bb = draw.textbbox((0, 0), text, font=font)
    return (bb[3] - bb[1]) + 6


def _code_png(path: str, title: str, lines: list, highlight: dict = None):
    """
    lines: list of (indent_level, text, color)
    highlight: {line_number: True} — lines with yellowish background
    """
    font     = _mono(14)
    font_sm  = _mono(11)
    pad_l    = 64   # gutter width
    pad_r    = 32
    pad_top  = 48   # tab bar height
    pad_bot  = 24

    tmp_img  = Image.new("RGB", (W, 100), BG)
    tmp_draw = ImageDraw.Draw(tmp_img)
    lh       = _line_height(font, tmp_draw)

    total_h = pad_top + len(lines) * lh + pad_bot
    img  = Image.new("RGB", (W, total_h), BG)
    draw = ImageDraw.Draw(img)

    # Tab bar
    draw.rectangle([0, 0, W, pad_top - 1], fill=BG_TAB)
    draw.rectangle([0, pad_top - 2, W, pad_top - 1], fill=(0, 122, 204))  # active tab indicator
    tab_font = _sans(12)
    draw.text((pad_l, 14), title, font=tab_font, fill=(204, 204, 204))

    # Gutter
    draw.rectangle([0, pad_top, pad_l - 10, total_h], fill=GUTTER)

    for i, (indent, text, color) in enumerate(lines):
        y = pad_top + i * lh

        # Highlight row
        if highlight and i in highlight:
            draw.rectangle([pad_l - 10, y, W, y + lh], fill=(40, 55, 40))

        # Line number
        ln_str = str(i + 1)
        bb = draw.textbbox((0, 0), ln_str, font=font_sm)
        lw = bb[2] - bb[0]
        draw.text((pad_l - 14 - lw, y + 2), ln_str, font=font_sm, fill=LINE_NUM)

        # Code text
        x = pad_l + indent * 20
        draw.text((x, y), text, font=font, fill=color)

    img.save(path, "PNG")
    print(f"  ✓ {os.path.basename(path)}")


def _terminal_png(path: str, title: str, segments: list):
    """
    segments: list of (text, color)
    color can be a tuple (r,g,b) or None (→ TERM_TEXT)
    """
    font    = _mono(13)
    pad     = 20
    pad_top = 44  # title bar

    tmp  = Image.new("RGB", (W, 100), TERM_BG)
    tmpd = ImageDraw.Draw(tmp)
    lh   = _line_height(font, tmpd)

    lines = []
    for text, color in segments:
        for sub in text.split("\n"):
            lines.append((sub, color or TERM_TEXT))

    total_h = pad_top + len(lines) * lh + pad * 2
    img  = Image.new("RGB", (W, total_h), TERM_BG)
    draw = ImageDraw.Draw(img)

    # Title bar
    draw.rectangle([0, 0, W, pad_top - 1], fill=(36, 36, 36))
    draw.ellipse([14, 14, 26, 26], fill=(255, 95, 86))
    draw.ellipse([34, 14, 46, 26], fill=(255, 189, 46))
    draw.ellipse([54, 14, 66, 26], fill=(39, 201, 63))
    tf = _sans(12)
    tb = draw.textbbox((0, 0), title, font=tf)
    draw.text(((W - (tb[2]-tb[0])) // 2, 14), title, font=tf, fill=(180, 180, 180))

    for i, (text, color) in enumerate(lines):
        y = pad_top + pad + i * lh
        draw.text((pad, y), text, font=font, fill=color)

    img.save(path, "PNG")
    print(f"  ✓ {os.path.basename(path)}")


# ── Screenshot B — config metadata ───────────────────────────────────────────

def gen_B():
    data = json.load(open("today/week_config.json", encoding="utf-8"))
    t = data["tracks"][0]  # afrofuturism-highlife-wave-2026

    lines = [
        (0, '{',                                        PUNCT),
        (1, f'"slug": "{t["slug"]}",',                 STR),
        (1, f'"title": "{t["title"][:65]}…",',         STR),
        (1, '"description": "From the rhythms of…",',  STR),
        (1, '"tags": [',                               PUNCT),
        (2, '"afrofuturism", "highlife",',             STR),
        (2, '"ai music", "no copyright", …',           STR),
        (1, '],',                                      PUNCT),
        (1, '"playlists": [',                          PUNCT),
        (2, f'"{t["playlists"][0]}",',                 STR),
        (2, f'"{t["playlists"][1]}"',                  STR),
        (1, '],',                                      PUNCT),
        (1, f'"scheduled_at": "{t.get("scheduled_at","")}",', STR),
        (1, '"madeForKids": false,',                   KW),
        (1, '"defaultLanguage": "en",',                STR),
        (1, '"defaultAudioLanguage": "en"',            STR),
        (0, '}',                                       PUNCT),
    ]
    _code_png(
        os.path.join(OUT_DIR, "B_config_metadata.png"),
        "config.json — track metadata",
        lines,
        highlight={9, 10, 11, 12},
    )


# ── Screenshot C — videos.insert ─────────────────────────────────────────────

def gen_C():
    lines = [
        (0, 'body = {',                                                 PUNCT),
        (1, '"snippet": {',                                             PUNCT),
        (2, '"title":               titre[:100],',                      TEXT),
        (2, '"description":         description,',                      TEXT),
        (2, '"tags":                tags,',                             TEXT),
        (2, '"categoryId":          "10",   # Music',                   STR),
        (2, '"defaultLanguage":     "fr",',                             STR),
        (2, '"defaultAudioLanguage":"fr",',                             STR),
        (1, '},',                                                       PUNCT),
        (1, '"status": {',                                              PUNCT),
        (2, '"privacyStatus":            "private",',                   STR),
        (2, '"publishAt":                publish_at,   # RFC3339 UTC',  STR),
        (2, '"selfDeclaredMadeForKids":  False,',                       KW),
        (1, '},',                                                       PUNCT),
        (0, '}',                                                        PUNCT),
        (0, '',                                                         TEXT),
        (0, 'media   = MediaFileUpload(chemin, chunksize=4*1024*1024, resumable=True)', TEXT),
        (0, 'requete = youtube.videos().insert(',                       FUNC),
        (1, 'part       = "snippet,status",',                          STR),
        (1, 'body       = body,',                                       TEXT),
        (1, 'media_body = media,',                                      TEXT),
        (0, ')',                                                        PUNCT),
        (0, 'response = requete.next_chunk()   # résumable upload',     COMMENT),
    ]
    _code_png(
        os.path.join(OUT_DIR, "C_videos_insert.png"),
        "modules/youtube.py — videos.insert()",
        lines,
        highlight={17, 18, 19, 20, 21},
    )


# ── Screenshot D — thumbnails.set ────────────────────────────────────────────

def gen_D():
    lines = [
        (0, '# Après video_id retourné par videos.insert()',            COMMENT),
        (0, 'if thumb_path and os.path.exists(thumb_path):',           KW),
        (1, 'youtube.thumbnails().set(',                               FUNC),
        (2, 'videoId    = video_id,',                                  TEXT),
        (2, 'media_body = MediaFileUpload(',                           TEXT),
        (3, 'thumb_path,',                                             STR),
        (3, 'mimetype = "image/jpeg",',                                STR),
        (2, '),',                                                      PUNCT),
        (1, ').execute()',                                             FUNC),
        (1, 'print(f"  → Thumbnail : {os.path.basename(thumb_path)}")', TEXT),
    ]
    _code_png(
        os.path.join(OUT_DIR, "D_thumbnails_set.png"),
        "modules/youtube.py — thumbnails.set()",
        lines,
        highlight={2, 3, 4, 5, 6, 7, 8},
    )


# ── Screenshot E — playlistItems.insert ──────────────────────────────────────

def gen_E():
    lines = [
        (0, 'def _ajouter_a_playlist(youtube, video_id, playlist_id):', FUNC),
        (1, 'youtube.playlistItems().insert(',                         FUNC),
        (2, 'part = "snippet",',                                       STR),
        (2, 'body = {',                                                PUNCT),
        (3, '"snippet": {',                                            PUNCT),
        (4, '"playlistId": playlist_id,',                             TEXT),
        (4, '"resourceId": {',                                         PUNCT),
        (5, '"kind":    "youtube#video",',                             STR),
        (5, '"videoId": video_id,',                                    TEXT),
        (4, '},',                                                      PUNCT),
        (3, '},',                                                      PUNCT),
        (2, '},',                                                      PUNCT),
        (1, ').execute()',                                             FUNC),
        (0, '',                                                        TEXT),
        (0, '# Résolution nom → ID via playlists_map.json (owner channel only)',  COMMENT),
        (0, 'pid = _resoudre_via_map(playlist_nom, base_dir)',          FUNC),
        (0, '_ajouter_a_playlist(youtube, video_id, pid)',              FUNC),
    ]
    _code_png(
        os.path.join(OUT_DIR, "E_playlist_insert.png"),
        "modules/youtube.py — playlistItems.insert()",
        lines,
        highlight={1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12},
    )


# ── Screenshot F — _authentifier() ───────────────────────────────────────────

def gen_F():
    lines = [
        (0, 'def _authentifier(base_dir):',                            FUNC),
        (1, 'token_path  = os.path.join(base_dir, OAUTH_TOKEN_PATH)',  TEXT),
        (1, 'secret_path = os.path.join(base_dir, CLIENT_SECRETS_PATH)', TEXT),
        (0, '',                                                         TEXT),
        (1, '# ── Load cached token ─────────────────────────────',    COMMENT),
        (1, 'if os.path.exists(token_path):',                          KW),
        (2, 'with open(token_path, "rb") as f:',                       KW),
        (3, 'creds = pickle.load(f)',                                  TEXT),
        (3, 'print("  → Token OAuth2 chargé depuis le cache.")',       STR),
        (0, '',                                                         TEXT),
        (1, '# ── Auto-refresh if expired ──────────────────────────', COMMENT),
        (1, 'if creds and creds.expired and creds.refresh_token:',     KW),
        (2, 'creds.refresh(google.auth.transport.requests.Request())', FUNC),
        (2, 'print("  → Token rafraîchi automatiquement.")',           STR),
        (0, '',                                                         TEXT),
        (1, '# ── First-time OAuth2 browser flow ──────────────────', COMMENT),
        (1, 'if not creds or not creds.valid:',                        KW),
        (2, 'flow = InstalledAppFlow.from_client_secrets_file(',       FUNC),
        (3, 'secret_path, SCOPES,',                                   TEXT),
        (2, ')',                                                       PUNCT),
        (2, 'creds = flow.run_local_server(port=0)',                   FUNC),
        (2, 'pickle.dump(creds, open(token_path, "wb"))',              FUNC),
        (0, '',                                                         TEXT),
        (1, 'return googleapiclient.discovery.build(',                 FUNC),
        (2, '"youtube", "v3", credentials=creds,',                     STR),
        (1, ')',                                                       PUNCT),
    ]
    _code_png(
        os.path.join(OUT_DIR, "F_authentifier.png"),
        "modules/youtube.py — _authentifier()",
        lines,
        highlight={5, 6, 7, 8, 11, 12, 13},
    )


# ── Screenshots G & H — terminal output ──────────────────────────────────────

def gen_G():
    segs = [
        ("assirem@mac assirem-music-prod-pipeline % ", TERM_PROM),
        ("python pipeline.py --upload --slug afrofuturism-highlife-wave-2026\n", TERM_TEXT),
        ("\n", None),
        ("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n", TERM_GREY),
        ("  Assirem Music PROD — Pipeline\n", TERM_BLUE),
        ("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n", TERM_GREY),
        ("\n", None),
        ("  → Authentification YouTube...\n", TERM_GREY),
        ("  → Token OAuth2 chargé depuis le cache.\n", TERM_GREEN),
        ("  → Token rafraîchi automatiquement.\n", TERM_GREEN),
    ]
    _terminal_png(
        os.path.join(OUT_DIR, "G_terminal_token.png"),
        "Terminal — zsh — assirem-music-prod-pipeline",
        segs,
    )


def gen_H():
    segs = [
        ("assirem@mac assirem-music-prod-pipeline % ", TERM_PROM),
        ("python pipeline.py --upload --slug afrofuturism-highlife-wave-2026\n", TERM_TEXT),
        ("\n", None),
        ("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n", TERM_GREY),
        ("  Assirem Music PROD — Pipeline\n", TERM_BLUE),
        ("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n", TERM_GREY),
        ("\n", None),
        ("  → Config  : today/week_config.json\n", TERM_GREY),
        ("  → Track   : afrofuturism-highlife-wave-2026\n", TERM_GREY),
        ("  → Vidéo   : output/afrofuturism-highlife-wave-2026/afrofuturism_highlife_wave_2026.mp4\n", TERM_GREY),
        ("  → Thumb   : output/afrofuturism-highlife-wave-2026/afrofuturism_highlife_wave_2026_thumb.jpg\n", TERM_GREY),
        ("\n", None),
        ("  → Authentification YouTube...\n", TERM_GREY),
        ("  → Token OAuth2 chargé depuis le cache.\n", TERM_GREEN),
        ("  → Token rafraîchi automatiquement.\n", TERM_GREEN),
        ("\n", None),
        ("  📊 Uploads aujourd'hui : 0 vidéo(s)\n", TERM_GREY),
        ("  → Playlist mappée : \"🌍 Afrofuturism & Afrobeats\" → ID: PLxxxxxxxxxxxxxx\n", TERM_GREY),
        ("  → Playlist mappée : \"🎵 Assirem Music PROD — All Tracks\" → ID: PLxxxxxxxxxxxxxx\n", TERM_GREY),
        ("\n", None),
        ("  → Upload : afrofuturism_highlife_wave_2026.mp4 (187.4 Mo) → publish 2026-05-13T06:15:00Z\n", TERM_GREY),
        ("     [████████████████████] 100%\n", TERM_BLUE),
        ("  → videoId : dQw4w9WgXcQ\n", TERM_YELL),
        ("  → Thumbnail : afrofuturism_highlife_wave_2026_thumb.jpg\n", TERM_GREY),
        ("  → Ajout playlist : 🌍 Afrofuturism & Afrobeats\n", TERM_GREY),
        ("  → Ajout playlist : 🎵 Assirem Music PROD — All Tracks\n", TERM_GREY),
        ("\n", None),
        ("  ✅  Upload terminé — afrofuturism-highlife-wave-2026\n", TERM_GREEN),
        ("      URL : https://www.youtube.com/watch?v=dQw4w9WgXcQ\n", TERM_BLUE),
    ]
    _terminal_png(
        os.path.join(OUT_DIR, "H_terminal_upload.png"),
        "Terminal — zsh — assirem-music-prod-pipeline",
        segs,
    )


# ── Run all ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"\nGénération des screenshots → {OUT_DIR}\n")
    gen_B()
    gen_C()
    gen_D()
    gen_E()
    gen_F()
    gen_G()
    gen_H()
    print(f"\n✅  {len(os.listdir(OUT_DIR))} fichiers générés dans compliance_screenshots/")
    print("   Screenshots manquants (YouTube Studio — à faire manuellement) :")
    print("   A  — Studio → channel name + owner account (top-right)")
    print("   I  — Studio → Content → video row")
    print("   J  — Studio → Video Details (title + thumbnail visible)")
