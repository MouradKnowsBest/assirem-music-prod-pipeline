"""
week_tracks_data.py
Templates pour les 25 tracks des jours 3-7 (les 10 jours 1-2 sont lus
depuis config.json par le générateur).

Format minimal par track :
  - slug, title, suno_title, suno_style, suno_lyrics, suno_vocal_gender
  - description, tags, playlists (liste, premier = primaire)
  - scenes (6 tuples (prompt, motion_strength))
  - category (trending | activity | world_music)
  - country / country_flag (si world_music)
  - activity_type (si activity)

Slot horaire (déterminé par index dans la liste, 5 slots/jour) :
  index%5 == 0 → 08:15  (morning chill)
  index%5 == 1 → 12:10  (lunch upbeat)
  index%5 == 2 → 16:13  (afternoon focus / workout)
  index%5 == 3 → 20:02  (evening dark / soulful)
  index%5 == 4 → 23:16  (night sleep / dark)
"""

TRACKS = [

    # ═══════════════════════════════════════════════════════════════════════
    # DAY 3 — Lundi 2026-04-27
    # ═══════════════════════════════════════════════════════════════════════

    # ── 11/35 — 08:15 — Tokyo Morning Café (lofi instrumental) ──────────────
    {
        "slug": "tokyo-morning-cafe-lofi-2026",
        "category": "activity",
        "activity_type": "focus",
        "title": "☕ Tokyo Morning Café — Lofi Coffee Vibes 2026 | Assirem Music PROD",
        "description": (
            "Slow Tokyo mornings — vinyl crackle, steam from your kettle, "
            "soft rain on the window. ☕\n\n"
            "Perfect lofi blend for slow Sunday wake-ups, quiet study sessions "
            "and lonely-but-cozy mornings.\n\n"
            "⏱️ Chapters:\n"
            "00:00 — Café opens\n01:30 — Steam & rain\n03:30 — Late morning drift\n\n"
            "🎧 Best for: study, focus, café vibes, slow mornings\n\n"
            "#LofiHipHop #StudyMusic #CafeVibes #TokyoMorning #AssiremMusicProd #NoCopyright"
        ),
        "tags": [
            "lofi hip hop", "study music", "tokyo cafe", "focus beats",
            "morning chill", "ai music", "assirem music prod", "no copyright", "2026 music",
        ],
        "playlists": [
            "📚 Focus, Lo-Fi & Coffee Work",
            "🌸 Pop, Chill & Indie Rock",
        ],
        "suno_title": "Tokyo Morning Café",
        "suno_style": (
            "lofi hip hop, japanese tea house, vinyl crackle, jazzy electric guitar, "
            "soft brushed drums, warm rhodes piano, 75 BPM, cozy, intimate, morning"
        ),
        "suno_exclude_styles": "trap, edm, dubstep, aggressive, heavy metal, country",
        "suno_vocal_gender": None,
        "suno_lyrics": "[Instrumental]",
        "suno_weirdness": 25,
        "suno_style_influence": 45,
        "intro_fade_sec": 3,
        "outro_fade_sec": 4,
        "short_start": 18,
        "scenes": [
            ("Wide establishing shot: tiny Tokyo café at dawn, paper lanterns glowing, steam from kettles, golden window light, cinematic 4K", 2),
            ("Slow pan over wooden counter: V60 dripper, vinyl record sleeve, dog-eared book, warm lamp, cinematic 4K", 2),
            ("Medium shot: young woman by window seat reading, latte in hand, soft morning light on her face, ultra detailed 4K", 2),
            ("Close-up: vinyl turntable spinning, dust motes in the lamp glow, needle in groove, macro cinematic 4K", 1),
            ("Medium shot: rain streaks down the window, barista pouring slowly behind, intimate atmosphere, cinematic 4K", 2),
            ("Wide final: Tokyo neon street viewed from inside the café, blue hour, lofi tranquility, 4K stunning", 2),
        ],
    },

    # ── 12/35 — 12:10 — Havana Heat (Latin salsa, female vocals) ────────────
    {
        "slug": "havana-heat-salsa-2026",
        "category": "trending",
        "title": "🌶️ Havana Heat — Latin Salsa Sunshine 2026 | Assirem Music PROD",
        "description": (
            "Drop everything and dance — Havana sunshine in your speakers. 🌶️\n\n"
            "Brassy salsa, congas and a voice you can't ignore. Your Tuesday lunch "
            "just got a lot louder.\n\n"
            "⏱️ Chapters:\n"
            "00:00 — Open the windows\n01:20 — First chorus\n03:00 — Brass break\n\n"
            "🎧 Best for: dancing, cooking, summer vibes, Latin lunch\n\n"
            "#Salsa #LatinMusic #Havana #DanceMusic #AssiremMusicProd #NoCopyright #2026"
        ),
        "tags": [
            "salsa", "latin music", "havana", "dance music",
            "summer vibes", "tropical", "ai music", "assirem music prod", "no copyright",
        ],
        "playlists": ["🌶️ Latin, Caribbean & Reggae"],
        "suno_title": "Havana Heat",
        "suno_style": (
            "salsa, latin pop, congas, timbales, piano guajira, brass section, "
            "upbeat, 120 BPM, tropical, dance, joyful, female lead voice"
        ),
        "suno_exclude_styles": "trap, edm, lofi, ambient, country, sad ballad",
        "suno_vocal_gender": "female",
        "suno_lyrics": (
            "[Verse 1]\n"
            "Sun is calling, drums are knocking\n"
            "Open the door and feel the heat\n"
            "Havana morning, hips are rocking\n"
            "I won't sleep until I move my feet\n\n"
            "[Chorus]\n"
            "Havana heat, Havana heat\n"
            "Takes me higher, sweeps me off my feet\n"
            "Havana heat, Havana heat\n"
            "Salsa nights and bossa beats\n\n"
            "[Verse 2]\n"
            "Brass is flying, drinks are pouring\n"
            "Streetlight glow on Malecón\n"
            "Smile so wide it ain't ignoring\n"
            "Every step a brand new song\n\n"
            "[Chorus]\n"
            "Havana heat, Havana heat\n"
            "Takes me higher, sweeps me off my feet\n"
            "Havana heat, Havana heat\n"
            "Salsa nights and bossa beats\n\n"
            "[Outro]\n"
            "Vamos a bailar, vamos a bailar\n"
            "Havana heat tonight"
        ),
        "suno_weirdness": 35,
        "suno_style_influence": 55,
        "intro_fade_sec": 1,
        "outro_fade_sec": 2,
        "short_start": 8,
        "scenes": [
            ("Wide establishing shot: Havana street at noon, pastel colonial walls, palm trees, classic 1950s car, vibrant cinematic 4K", 3),
            ("Slow camera travel through Malecón promenade, ocean spray, dancers in red flowing dresses, golden sunlight, cinematic 4K", 4),
            ("Medium shot: Cuban woman in red dress dancing salsa on cobblestones, brass band behind her, ultra detailed 4K", 5),
            ("Close-up: hands on conga drums in slow motion, sweat beads, sun glinting off rings, macro cinematic 4K", 3),
            ("Medium shot: rooftop salsa party at sunset, twirling couple, tropical drinks, neon signs in background, cinematic 4K", 4),
            ("Wide final: Havana skyline glowing pink at sunset, dancers silhouetted on rooftop, joyful cityscape, 4K stunning", 3),
        ],
    },

    # ── 13/35 — 16:13 — Ibiza Deep House (electronic instrumental) ──────────
    {
        "slug": "ibiza-deep-house-2026",
        "category": "trending",
        "title": "🌊 Ibiza Deep House — Sunset Session 2026 | Assirem Music PROD",
        "description": (
            "The sun is setting over Cala d'Hort and the bassline never stops. 🌊\n\n"
            "Rolling deep house for late afternoons that turn into long nights. "
            "Pure groove, zero stress.\n\n"
            "⏱️ Chapters:\n"
            "00:00 — Soundcheck\n01:30 — The drop\n03:30 — Sunset peak\n\n"
            "🎧 Best for: chill afternoon, sunset drives, beach club, focus\n\n"
            "#DeepHouse #Ibiza #ElectronicMusic #SunsetSession #AssiremMusicProd #NoCopyright"
        ),
        "tags": [
            "deep house", "ibiza", "electronic music", "sunset session",
            "house music", "chill electronic", "ai music", "assirem music prod", "no copyright",
        ],
        "playlists": ["🔮 Electronic, House & Techno"],
        "suno_title": "Ibiza Deep House",
        "suno_style": (
            "deep house, minimal techno, rolling 4x4 kick, sub bass, warm analog pads, "
            "filter sweeps, 122 BPM, hypnotic, sunset Ibiza, underground"
        ),
        "suno_exclude_styles": "trap, hip hop, acoustic, country, hard rock",
        "suno_vocal_gender": None,
        "suno_lyrics": "[Instrumental]",
        "suno_weirdness": 30,
        "suno_style_influence": 50,
        "intro_fade_sec": 4,
        "outro_fade_sec": 4,
        "short_start": 60,
        "scenes": [
            ("Wide establishing shot: Ibiza cliff at sunset, infinity pool, beach club crowd, orange sky, cinematic 4K", 3),
            ("Slow travel: rolling waves crashing on white rocks, Cala d'Hort silhouette, warm golden hour, cinematic 4K", 3),
            ("Medium shot: DJ behind decks at open-air club, hands on filter knob, fading sun on his face, ultra detailed 4K", 3),
            ("Close-up: vinyl needle dropping on a 12-inch record, club lights bokeh behind, macro cinematic 4K", 2),
            ("Medium shot: dancers raising hands at sunset, silhouettes against pink horizon, euphoric, cinematic 4K", 5),
            ("Wide final: full beach club view, sun half below the sea, palm tree silhouettes, 4K stunning", 3),
        ],
    },

    # ── 14/35 — 20:02 — Neon Africa (Afrofuturism instrumental) ─────────────
    {
        "slug": "neon-africa-afrofuturism-2026",
        "category": "trending",
        "title": "🌌 Neon Africa — Afrofuturism Cosmic Tribe 2026 | Assirem Music PROD",
        "description": (
            "Africa in 2099 — kora meets synthesizers, ancient drums meet starlight. 🌌\n\n"
            "Afrofuturism at its most cinematic — Lagos to Mars in one playlist.\n\n"
            "⏱️ Chapters:\n"
            "00:00 — Liftoff\n01:30 — The Cosmic Tribe\n04:00 — Neon Sahara\n\n"
            "🎧 Best for: focus, sci-fi vibes, futuristic energy, world music fans\n\n"
            "#Afrofuturism #NeonAfrica #Amapiano #CosmicMusic #AssiremMusicProd #NoCopyright"
        ),
        "tags": [
            "afrofuturism", "neon africa", "amapiano", "cosmic tribe",
            "afro electronic", "world music", "ai music", "assirem music prod", "no copyright",
        ],
        "playlists": ["🌍 Afrofuturism", "🌏 World Music"],
        "suno_title": "Neon Africa",
        "suno_style": (
            "afrofuturism, amapiano, neo-soul synth, kora-meets-synthesizer, "
            "log drum bass, cosmic percussion, 104 BPM, ritual, neon Africa, space tribe"
        ),
        "suno_exclude_styles": "country, classical, sad ballad, polka, lofi",
        "suno_vocal_gender": None,
        "suno_lyrics": "[Instrumental]",
        "suno_weirdness": 45,
        "suno_style_influence": 58,
        "intro_fade_sec": 2,
        "outro_fade_sec": 3,
        "short_start": 12,
        "scenes": [
            ("Wide establishing shot: futuristic Lagos skyline at dusk, neon-lit skyscrapers next to baobab trees, holographic dancers, cinematic 4K", 4),
            ("Slow travel through neon Sahara dunes at twilight, robotic camels under glowing constellations, cinematic 4K", 3),
            ("Medium shot: African dancer in metallic geometric mask, neon body paint glowing, performing ritual under starfield, ultra detailed 4K", 4),
            ("Close-up: hands playing a holographic kora, strings glowing electric blue, cosmic dust around fingers, macro cinematic 4K", 3),
            ("Medium shot: futuristic griot in ceremonial robe surrounded by floating amapiano log drums, electric tribe, cinematic 4K", 3),
            ("Wide final: African continent seen from low orbit, illuminated by tribal neon patterns, planet glowing alive, 4K stunning", 2),
        ],
    },

    # ── 15/35 — 23:16 — Eclipse (dark cinematic orchestral) ─────────────────
    {
        "slug": "eclipse-cinematic-dark-2026",
        "category": "trending",
        "title": "🌑 Eclipse — Dark Cinematic Orchestral 2026 | Assirem Music PROD",
        "description": (
            "When the world holds its breath — strings tremble, brass rises. 🌑\n\n"
            "Dark cinematic orchestral for late-night thinking, geopolitical drama, "
            "and the weight of inevitable moments.\n\n"
            "⏱️ Chapters:\n"
            "00:00 — Silence before\n01:45 — First tremor\n03:30 — Total eclipse\n\n"
            "🎧 Best for: cinematic playlists, deep focus, dramatic moods, late nights\n\n"
            "#CinematicMusic #OrchestralEpic #DarkClassical #FilmScore #AssiremMusicProd #NoCopyright"
        ),
        "tags": [
            "cinematic music", "orchestral epic", "dark classical", "film score",
            "dramatic music", "ai music", "assirem music prod", "no copyright", "2026 music",
        ],
        "playlists": ["🕊️ Cinematic & Orchestral", "🌘 Dark Vibes & Night Drive"],
        "suno_title": "Eclipse",
        "suno_style": (
            "cinematic orchestral, dark epic, tremolo strings, brass stabs, choir layers, "
            "deep taikos, 72 BPM, tense, geopolitical drama, apocalyptic beauty"
        ),
        "suno_exclude_styles": "trap, lofi, edm, country, happy pop, dance",
        "suno_vocal_gender": None,
        "suno_lyrics": "[Instrumental]",
        "suno_weirdness": 30,
        "suno_style_influence": 55,
        "intro_fade_sec": 4,
        "outro_fade_sec": 5,
        "short_start": 90,
        "scenes": [
            ("Wide establishing shot: total solar eclipse over an ancient cathedral, corona blazing, deep purple sky, cinematic 4K", 2),
            ("Slow travel through war-room corridor, holographic maps glowing red on walls, tension visible, cinematic 4K", 3),
            ("Medium shot: silhouetted conductor leading orchestra in candle-lit hall, strings raised, ultra detailed 4K", 3),
            ("Close-up: timpani mallet striking drum head in slow motion, dust exploding off skin, macro cinematic 4K", 4),
            ("Medium shot: lone figure standing on cliff in storm, watching distant city, cape flowing, cinematic 4K", 3),
            ("Wide final: Earth seen from space mid-eclipse, shadow sweeping across continents, ancient and vast, 4K stunning", 2),
        ],
    },

    # ═══════════════════════════════════════════════════════════════════════
    # DAY 4 — Mardi 2026-04-28
    # ═══════════════════════════════════════════════════════════════════════

    # ── 16/35 — 08:15 — Rainy Bedroom Lofi (soft female vocals) ─────────────
    {
        "slug": "rainy-bedroom-lofi-2026",
        "category": "activity",
        "activity_type": "focus",
        "title": "🌧️ Rainy Bedroom Lofi — Soft Vocal Chill 2026 | Assirem Music PROD",
        "description": (
            "Stay in bed. The world can wait. 🌧️\n\n"
            "Bedroom lofi with soft female vocals for rainy mornings, slow Tuesdays "
            "and warm-blanket states of mind.\n\n"
            "⏱️ Chapters:\n"
            "00:00 — First raindrops\n01:15 — Chorus\n03:00 — Half asleep\n\n"
            "🎧 Best for: study breaks, rainy days, soft mornings, cozy playlists\n\n"
            "#LofiPop #BedroomPop #RainyDay #ChillMusic #AssiremMusicProd #NoCopyright"
        ),
        "tags": [
            "lofi pop", "bedroom pop", "rainy day", "soft vocals",
            "chill music", "morning chill", "ai music", "assirem music prod", "no copyright",
        ],
        "playlists": ["📚 Focus, Lo-Fi & Coffee Work", "🌸 Pop, Chill & Indie Rock"],
        "suno_title": "Rainy Bedroom",
        "suno_style": (
            "lofi pop, bedroom pop, soft female vocals, acoustic guitar, "
            "warm tape hiss, gentle piano, 72 BPM, intimate, cozy, rainy morning"
        ),
        "suno_exclude_styles": "trap, edm, drill, aggressive, country, heavy drums",
        "suno_vocal_gender": "female",
        "suno_lyrics": (
            "[Verse 1]\n"
            "Soft grey light through the curtain crack\n"
            "Phone on silent, time turns its back\n"
            "Rain on the roof writing a song\n"
            "Maybe today I'll just stay home\n\n"
            "[Chorus]\n"
            "Rainy bedroom, soft and slow\n"
            "Nowhere to be, nowhere to go\n"
            "Just the kettle and the radio\n"
            "Rainy bedroom, soft and slow\n\n"
            "[Verse 2]\n"
            "Cup of tea cooling on the floor\n"
            "Sweater I forgot was yours\n"
            "Pages of a book I never read\n"
            "Sun is rising in my head\n\n"
            "[Chorus]\n"
            "Rainy bedroom, soft and slow\n"
            "Nowhere to be, nowhere to go\n"
            "Just the kettle and the radio\n"
            "Rainy bedroom, soft and slow\n\n"
            "[Outro]\n"
            "Stay a little longer, stay a little longer"
        ),
        "suno_weirdness": 25,
        "suno_style_influence": 45,
        "intro_fade_sec": 3,
        "outro_fade_sec": 4,
        "short_start": 15,
        "scenes": [
            ("Wide establishing shot: cozy bedroom on rainy morning, fairy lights still on, unmade bed, soft grey light, cinematic 4K", 1),
            ("Slow pan over bedside table: cooling tea cup, open book, vinyl record, fogged window, cinematic 4K", 1),
            ("Medium shot: young woman wrapped in oversized sweater, looking at rain through window, soft skin glow, ultra detailed 4K", 2),
            ("Close-up: raindrops sliding down window in slow motion, bedroom blurred warm behind glass, macro cinematic 4K", 1),
            ("Medium shot: hands holding warm mug, knit sleeves, steam rising, natural soft window light, cinematic 4K", 1),
            ("Wide final: bedroom from above, person sleeping under thick blankets, rain still falling outside, 4K stunning", 1),
        ],
    },

    # ── 17/35 — 12:10 — Neo City Pop Tokyo (female vocals) ──────────────────
    {
        "slug": "neo-city-pop-tokyo-2026",
        "category": "trending",
        "title": "🌆 Neo City Pop Tokyo — Summer Drive 2026 | Assirem Music PROD",
        "description": (
            "Tokyo at golden hour, windows down, summer in your chest. 🌆\n\n"
            "Modern city pop with 80s nostalgia and 2026 polish — for the perfect "
            "Tuesday lunch break.\n\n"
            "⏱️ Chapters:\n"
            "00:00 — Sun on the dashboard\n01:10 — Chorus\n03:00 — Bridge\n\n"
            "🎧 Best for: city drives, summer vibes, indie pop fans, productive lunch\n\n"
            "#CityPop #NeoCityPop #TokyoVibes #IndiePop #AssiremMusicProd #NoCopyright #2026"
        ),
        "tags": [
            "city pop", "neo city pop", "tokyo vibes", "indie pop",
            "summer music", "synth pop", "ai music", "assirem music prod", "no copyright",
        ],
        "playlists": ["🌸 Pop, Chill & Indie Rock"],
        "suno_title": "Neo City Pop Tokyo",
        "suno_style": (
            "neo city pop, japanese influenced, smooth synth bass, electric piano, "
            "saxophone hook, 98 BPM, summer, nostalgic shimmer, female lead voice"
        ),
        "suno_exclude_styles": "trap, drill, aggressive, country, lofi, ambient",
        "suno_vocal_gender": "female",
        "suno_lyrics": (
            "[Verse 1]\n"
            "Tokyo glows under the noon sun\n"
            "Top down driving, summer just begun\n"
            "Convenience store lemonade\n"
            "Every red light feels like a parade\n\n"
            "[Pre-Chorus]\n"
            "I don't know where we're going\n"
            "But the playlist keeps on rolling\n\n"
            "[Chorus]\n"
            "Neo city, neo city pop\n"
            "Summer don't you ever stop\n"
            "Skyline shining, hands on top\n"
            "Neo city, neo city pop\n\n"
            "[Verse 2]\n"
            "Crossing Shibuya like the world is ours\n"
            "Vending machines and pastel towers\n"
            "Salt on my lips from the bay\n"
            "Forever feels close enough to stay\n\n"
            "[Chorus]\n"
            "Neo city, neo city pop\n"
            "Summer don't you ever stop\n"
            "Skyline shining, hands on top\n"
            "Neo city, neo city pop\n\n"
            "[Outro]\n"
            "Tokyo, Tokyo, never let me down"
        ),
        "suno_weirdness": 35,
        "suno_style_influence": 52,
        "intro_fade_sec": 2,
        "outro_fade_sec": 3,
        "short_start": 12,
        "scenes": [
            ("Wide establishing shot: Tokyo expressway at golden hour, classic 80s convertible, neon billboards, palm trees, cinematic 4K", 4),
            ("Slow travel: dashboard view of Shibuya scramble crossing, sun flare on chrome, retro stickers, cinematic 4K", 4),
            ("Medium shot: young Japanese woman driver smiling, sunglasses, hair in the wind, ultra detailed 4K", 3),
            ("Close-up: cassette tape sliding into car deck, hand turning volume knob, retro details, macro cinematic 4K", 2),
            ("Medium shot: Tokyo Bay rooftop at sunset, friends laughing, drinks raised, neon city behind them, cinematic 4K", 4),
            ("Wide final: aerial of Tokyo at twilight, river of red and white lights, summer haze, 4K stunning", 3),
        ],
    },

    # ── 18/35 — 16:13 — Iron Mindset (hard trap gym, instrumental) ──────────
    {
        "slug": "iron-mindset-hard-trap-2026",
        "category": "activity",
        "activity_type": "gym",
        "title": "🏋️ Iron Mindset — Hard Trap Gym Motivation 2026 | Assirem Music PROD",
        "description": (
            "Forge the mindset before you forge the body. 🏋️\n\n"
            "144 BPM of skull-rattling 808s and aggressive synths — for the sets "
            "you don't want to do but you will anyway.\n\n"
            "⏱️ Chapters:\n"
            "00:00 — Warmup\n01:00 — Working sets\n02:30 — Last rep\n\n"
            "🎧 Best for: heavy lifting, HIIT, pre-workout, mindset reps\n\n"
            "#GymMusic #HardTrap #IronMindset #BeastMode #AssiremMusicProd #NoCopyright"
        ),
        "tags": [
            "gym music", "hard trap", "iron mindset", "beast mode",
            "workout music", "808", "ai music", "assirem music prod", "no copyright",
        ],
        "playlists": ["💪 Workout, Gym & Motivation", "🌘 Dark Vibes & Night Drive"],
        "suno_title": "Iron Mindset",
        "suno_style": (
            "hard trap, gym beats, distorted 808 sub bass, aggressive saw lead, "
            "rolling hi-hat triplets, 144 BPM, masculine energy, savage mode, dark"
        ),
        "suno_exclude_styles": "lofi, ambient, acoustic, soft, jazz, classical, country",
        "suno_vocal_gender": None,
        "suno_lyrics": "[Instrumental]",
        "suno_weirdness": 50,
        "suno_style_influence": 60,
        "intro_fade_sec": 1,
        "outro_fade_sec": 2,
        "short_start": 5,
        "scenes": [
            ("Wide establishing shot: industrial concrete gym, single red light overhead, chains and iron everywhere, raw atmosphere, cinematic 4K", 3),
            ("Slow camera low across rubber floor: chalk dust rising from dropped 100kg bar, harsh red lighting, cinematic 4K", 4),
            ("Medium shot: athlete mid heavy deadlift, every vein and muscle locked, motion blur on bar, ultra detailed 4K", 7),
            ("Close-up: callused hand gripping knurled barbell, chalk and sweat, white knuckles, macro cinematic 4K", 2),
            ("Medium shot: athlete dropping bar after PR lift, primal scream, chalk cloud exploding, cinematic 4K", 6),
            ("Wide final: lone athlete silhouette in empty gym, weight rack behind, never-stop body language, 4K stunning", 2),
        ],
    },

    # ── 19/35 — 20:02 — Kabyle Oud Desert Night (Maghreb instrumental) ──────
    {
        "slug": "kabyle-oud-desert-night-2026",
        "category": "world_music",
        "country": "Algérie",
        "country_flag": "🇩🇿",
        "title": "🇩🇿 Kabyle Oud — Desert Night Maghreb 2026 | Assirem Music PROD",
        "description": (
            "Oud strings under desert stars — the soul of Tamazgha at midnight. 🌙\n\n"
            "Algerian Kabyle and Maghreb roots, oud and bendir layered with dark "
            "soul ambiance. Tineghren, ancestral.\n\n"
            "⏱️ Chapters:\n"
            "00:00 — Desert wind\n02:00 — Oud awakens\n04:00 — Tribal pulse\n\n"
            "🎧 Best for: oriental vibes, Maghreb pride, evening reflection, world fans\n\n"
            "#OudMusic #Kabyle #MaghrebMusic #Oriental #Tamazgha #AssiremMusicProd #NoCopyright"
        ),
        "tags": [
            "oud music", "kabyle", "maghreb music", "oriental",
            "amazigh", "tamazgha", "world music", "assirem music prod", "no copyright",
        ],
        "playlists": ["🌙 Oriental, Oud & Maghreb", "🌏 World Music"],
        "suno_title": "Kabyle Oud Night",
        "suno_style": (
            "oriental, algerian kabyle, oud lead, bendir frame drum, maqam hijaz, "
            "gnawa undertones, dark soul, 80 BPM, desert night, mystical, amazigh"
        ),
        "suno_exclude_styles": "edm, trap, country, western pop, drill, electronic dance",
        "suno_vocal_gender": None,
        "suno_lyrics": "[Instrumental]",
        "suno_weirdness": 30,
        "suno_style_influence": 50,
        "intro_fade_sec": 4,
        "outro_fade_sec": 4,
        "short_start": 30,
        "scenes": [
            ("Wide establishing shot: Algerian Sahara at night, infinite dunes under starfield, Milky Way blazing, lone Berber tent, 4K", 2),
            ("Slow travel: campfire crackling in foreground, men in hooded burnous around it, blue desert behind, cinematic 4K", 2),
            ("Medium shot: Kabyle elder playing oud by firelight, eyes closed, tattooed hands on strings, ultra detailed 4K", 2),
            ("Close-up: oud strings vibrating in slow motion, fingers in motion, fire glow on wood grain, macro cinematic 4K", 2),
            ("Medium shot: Berber woman in indigo veil dancing slow circles, silver jewelry catching firelight, cinematic 4K", 3),
            ("Wide final: dawn rising over Atlas mountains beyond the dunes, tent still glowing inside, 4K stunning", 2),
        ],
    },

    # ── 20/35 — 23:16 — Night Drive Phonk (dark phonk instrumental) ─────────
    {
        "slug": "night-drive-phonk-2026",
        "category": "trending",
        "title": "🚗 Night Drive Phonk — Midnight Highway 2026 | Assirem Music PROD",
        "description": (
            "Empty highway, headlights cutting through fog, foot heavy on the pedal. 🚗\n\n"
            "Pure midnight phonk for nights you don't want to end and questions you "
            "don't want to answer.\n\n"
            "⏱️ Chapters:\n"
            "00:00 — Engine on\n01:30 — Highway hypnosis\n03:30 — Sunrise on the horizon\n\n"
            "🎧 Best for: night drives, gym, focus, dark vibes\n\n"
            "#PhonkMusic #NightDrive #DarkPhonk #MidnightVibes #AssiremMusicProd #NoCopyright"
        ),
        "tags": [
            "phonk", "night drive", "dark phonk", "midnight vibes",
            "drift music", "ai music", "assirem music prod", "no copyright", "2026 music",
        ],
        "playlists": ["🌘 Dark Vibes & Night Drive"],
        "suno_title": "Night Drive Phonk",
        "suno_style": (
            "dark phonk, night drive, distorted 808 bass, screeching cowbell, "
            "miami phonk influence, chopped vocal samples, 140 BPM, headlights, drift"
        ),
        "suno_exclude_styles": "lofi, ambient, classical, country, soft pop, acoustic",
        "suno_vocal_gender": None,
        "suno_lyrics": "[Instrumental]",
        "suno_weirdness": 50,
        "suno_style_influence": 58,
        "intro_fade_sec": 1,
        "outro_fade_sec": 2,
        "short_start": 8,
        "scenes": [
            ("Wide establishing shot: empty highway at midnight, headlights piercing fog, neon overpass in distance, cinematic 4K", 4),
            ("Slow travel: low side angle of black sports car drifting through tunnel, sparks on wall, cinematic 4K", 6),
            ("Medium shot: driver in leather gloves, hands on wheel, neon dashboard glow on his face, ultra detailed 4K", 3),
            ("Close-up: tachometer needle climbing past redline, glow on glass, motion blur, macro cinematic 4K", 3),
            ("Medium shot: rear view of car drifting on mountain pass, smoke from tires, full moon above, cinematic 4K", 6),
            ("Wide final: car stopped at cliff overlook at first light, city below, lone driver outside, 4K stunning", 2),
        ],
    },

    # ═══════════════════════════════════════════════════════════════════════
    # DAY 5 — Mercredi 2026-04-29
    # ═══════════════════════════════════════════════════════════════════════

    # ── 21/35 — 08:15 — Bali Gamelan Sunrise (world instrumental) ───────────
    {
        "slug": "bali-gamelan-sunrise-2026",
        "category": "world_music",
        "country": "Indonésie",
        "country_flag": "🇮🇩",
        "title": "🌅 Bali Gamelan Sunrise — Balinese Ceremony 2026 | Assirem Music PROD",
        "description": (
            "Sunrise over the rice terraces of Ubud — gamelan bells call the day. 🌅\n\n"
            "Traditional Balinese gamelan, ceremonial and meditative — the oldest "
            "morning music humanity ever made.\n\n"
            "⏱️ Chapters:\n"
            "00:00 — First light\n02:00 — Temple bells\n04:30 — Ceremony begins\n\n"
            "🎧 Best for: meditation, yoga, world music, slow mornings\n\n"
            "#Gamelan #BaliMusic #WorldMusic #IndonesianMusic #AssiremMusicProd #NoCopyright"
        ),
        "tags": [
            "gamelan", "bali music", "world music", "indonesian",
            "meditation music", "morning ceremony", "ai music", "assirem music prod", "no copyright",
        ],
        "playlists": ["🌏 World Music", "🧘 Meditation, Sleep & Wellness"],
        "suno_title": "Bali Gamelan Sunrise",
        "suno_style": (
            "balinese gamelan, metallophones, gongs, pelog tuning, ceremonial, "
            "meditative, 63 BPM, sunrise ritual, traditional indonesia, spiritual"
        ),
        "suno_exclude_styles": "edm, trap, drill, western pop, rock, electronic",
        "suno_vocal_gender": None,
        "suno_lyrics": "[Instrumental]",
        "suno_weirdness": 30,
        "suno_style_influence": 45,
        "intro_fade_sec": 4,
        "outro_fade_sec": 4,
        "short_start": 25,
        "scenes": [
            ("Wide establishing shot: Ubud rice terraces at sunrise, golden mist over green steps, distant volcano, cinematic 4K", 2),
            ("Slow travel through Balinese temple courtyard, stone gates, frangipani blossoms falling, soft light, cinematic 4K", 2),
            ("Medium shot: Balinese musicians in white robes around gamelan ensemble, mallets striking metallophones, ultra detailed 4K", 2),
            ("Close-up: bronze gong vibrating in slow motion, sunlight glinting on hammered surface, macro cinematic 4K", 1),
            ("Medium shot: priestess in lace ceremonial dress walking through morning mist with offerings, cinematic 4K", 2),
            ("Wide final: full sunrise over Mount Agung, temple silhouettes, mist burning off rice fields, 4K stunning", 2),
        ],
    },

    # ── 22/35 — 12:10 — Paris sous la Pluie (chanson française, female) ─────
    {
        "slug": "paris-sous-la-pluie-2026",
        "category": "trending",
        "title": "☔ Paris sous la Pluie — Chanson Française 2026 | Assirem Music PROD",
        "description": (
            "Paris quand il pleut, un café, un imperméable beige et tes pensées. ☔\n\n"
            "Chanson française moderne — guitare claire, piano fragile, et une voix "
            "qui sait ce que c'est de manquer quelqu'un à l'heure du déjeuner.\n\n"
            "⏱️ Chapitres:\n"
            "00:00 — Premier verre\n01:20 — Refrain\n03:00 — Pont mélancolique\n\n"
            "🎧 Idéal pour : café-déjeuner, playlists romantiques, pop française\n\n"
            "#PopFrançaise #ChansonFrançaise #ParisVibes #AssiremMusicProd #NoCopyright #2026"
        ),
        "tags": [
            "pop française", "chanson française", "paris vibes", "musique française",
            "indie pop fr", "ai music", "assirem music prod", "no copyright", "2026",
        ],
        "playlists": ["🇫🇷 Pop Française", "🌸 Pop, Chill & Indie Rock"],
        "suno_title": "Paris sous la Pluie",
        "suno_style": (
            "chanson française moderne, indie pop, guitare arpégée, piano fragile, "
            "soft drums, accordéon discret, 92 BPM, romantique, parisien, voix féminine"
        ),
        "suno_exclude_styles": "trap, edm, drill, country, heavy metal, aggressive",
        "suno_vocal_gender": "female",
        "suno_lyrics": (
            "[Couplet 1]\n"
            "Il pleut sur Paris à midi pile\n"
            "Je marche seule rue de Rivoli\n"
            "Ton parapluie est resté chez moi\n"
            "Je n'sais pas pourquoi je pense à toi\n\n"
            "[Pré-Refrain]\n"
            "Le ciel pleure plus fort que moi\n"
            "Mais on dirait qu'il sait pour toi\n\n"
            "[Refrain]\n"
            "Paris sous la pluie, Paris sous la pluie\n"
            "Tu n'es plus là mais ta voix me suit\n"
            "Paris sous la pluie, Paris sous la pluie\n"
            "Je danse toute seule à minuit\n\n"
            "[Couplet 2]\n"
            "Le café est tiède, le serveur sourit\n"
            "Je commande deux verres par habitude\n"
            "Le tien restera plein cet après-midi\n"
            "C'est comme ça qu'on dit la solitude\n\n"
            "[Refrain]\n"
            "Paris sous la pluie, Paris sous la pluie\n"
            "Tu n'es plus là mais ta voix me suit\n"
            "Paris sous la pluie, Paris sous la pluie\n"
            "Je danse toute seule à minuit\n\n"
            "[Outro]\n"
            "Reviens, reviens, reviens"
        ),
        "suno_weirdness": 32,
        "suno_style_influence": 48,
        "intro_fade_sec": 3,
        "outro_fade_sec": 4,
        "short_start": 14,
        "scenes": [
            ("Wide establishing shot: rue de Rivoli in Paris at noon, light rain, classic Haussmann buildings, wet cobblestones, cinematic 4K", 2),
            ("Slow travel: Café de Flore through rain-streaked window, terrace with closed umbrellas, cinematic 4K", 2),
            ("Medium shot: young Parisian woman alone at café table, looking out window, beige trench coat, ultra detailed 4K", 2),
            ("Close-up: two cups of espresso on marble table, one untouched, macro cinematic 4K", 1),
            ("Medium shot: woman walking on Pont Alexandre III in rain, scarf flying, Eiffel Tower behind, cinematic 4K", 2),
            ("Wide final: Parisian skyline through rain, glistening rooftops at midday, melancholic beauty, 4K stunning", 2),
        ],
    },

    # ── 23/35 — 16:13 — Cyberpunk Focus (dark electronic instrumental) ──────
    {
        "slug": "cyberpunk-focus-coding-2026",
        "category": "activity",
        "activity_type": "coding",
        "title": "💻 Cyberpunk Focus — Dark Coding Electronic 2026 | Assirem Music PROD",
        "description": (
            "Hack the night, ship the code. 💻\n\n"
            "Dark cyberpunk electronic for deep coding, late dev sprints, and "
            "dystopian-vibe focus sessions.\n\n"
            "⏱️ Chapters:\n"
            "00:00 — Boot sequence\n01:00 — Flow state\n03:30 — Deploy\n\n"
            "🎧 Best for: coding, AI dev, hackathons, dark focus\n\n"
            "#Cyberpunk #CodingMusic #ElectronicFocus #DevBeats #AssiremMusicProd #NoCopyright"
        ),
        "tags": [
            "cyberpunk", "coding music", "electronic focus", "dev beats",
            "industrial electronic", "ai music", "assirem music prod", "no copyright",
        ],
        "playlists": ["🔮 Electronic, House & Techno", "📚 Focus, Lo-Fi & Coffee Work"],
        "suno_title": "Cyberpunk Focus",
        "suno_style": (
            "cyberpunk electronic, industrial synth, glitchy arp, driving pulse, "
            "98 BPM, neon dystopia, dark future, focus, AI hacking, dystopian"
        ),
        "suno_exclude_styles": "country, lofi soft, acoustic, jazz, classical",
        "suno_vocal_gender": None,
        "suno_lyrics": "[Instrumental]",
        "suno_weirdness": 45,
        "suno_style_influence": 55,
        "intro_fade_sec": 2,
        "outro_fade_sec": 3,
        "short_start": 10,
        "scenes": [
            ("Wide establishing shot: cyberpunk night city, megacorp towers, holograms, rain on neon streets, cinematic 4K", 4),
            ("Slow travel through dark hacker den, walls of monitors with green code rain, cables everywhere, cinematic 4K", 3),
            ("Medium shot: hooded coder at curved ultrawide screen, code reflected in cyberpunk goggles, ultra detailed 4K", 3),
            ("Close-up: mechanical keyboard keys depressing in rapid slow motion, RGB underglow, macro cinematic 4K", 4),
            ("Medium shot: server racks pulsing with light, AI holograms floating, dystopian glow, cinematic 4K", 3),
            ("Wide final: hacker silhouette against neon megacity skyline at 3 AM, drone flying past, 4K stunning", 3),
        ],
    },

    # ── 24/35 — 20:02 — Neo Soul Lounge (hip hop neo soul, female) ──────────
    {
        "slug": "neo-soul-lounge-2026",
        "category": "trending",
        "title": "🎤 Neo Soul Lounge — Late Night R&B 2026 | Assirem Music PROD",
        "description": (
            "Velvet voice, jazz chords, and a glass of red wine you forgot to finish. 🎤\n\n"
            "Neo soul meets hip-hop poetry — the kind of evening soundtrack that "
            "makes you call someone you shouldn't.\n\n"
            "⏱️ Chapters:\n"
            "00:00 — Late arrival\n01:15 — Chorus\n03:00 — Bridge confessions\n\n"
            "🎧 Best for: dinner playlists, R&B fans, evening reflection, intimate vibes\n\n"
            "#NeoSoul #RnB #HipHopSoul #LateNightMusic #AssiremMusicProd #NoCopyright"
        ),
        "tags": [
            "neo soul", "rnb", "hip hop soul", "late night music",
            "soul music", "ai music", "assirem music prod", "no copyright", "2026 music",
        ],
        "playlists": ["🎤 Hip-Hop, Rap & R&B", "🌘 Dark Vibes & Night Drive"],
        "suno_title": "Neo Soul Lounge",
        "suno_style": (
            "neo soul, hip hop, warm rhodes piano, brushed drums, smooth bass, "
            "poetic flow, 85 BPM, introspective, soulful, late night, female lead voice"
        ),
        "suno_exclude_styles": "edm, drill, country, hard trap, aggressive, polka",
        "suno_vocal_gender": "female",
        "suno_lyrics": (
            "[Verse 1]\n"
            "Smoke is curling from a candle low\n"
            "Vinyl spinning records I should've thrown\n"
            "Wine is warm but the night is colder\n"
            "Eight years older but I never told her\n\n"
            "[Pre-Chorus]\n"
            "Rhodes is whispering my secrets back\n"
            "Bassline knows me on a different track\n\n"
            "[Chorus]\n"
            "Neo soul lounge, neo soul lounge\n"
            "Where every silence has its own sound\n"
            "Neo soul lounge, neo soul lounge\n"
            "Lost me a little to find me now\n\n"
            "[Verse 2]\n"
            "Lipstick stain on the rim of glass\n"
            "Memory dancing in slow motion class\n"
            "Saxophone crying through the smoky air\n"
            "Telling truths I never dared\n\n"
            "[Chorus]\n"
            "Neo soul lounge, neo soul lounge\n"
            "Where every silence has its own sound\n"
            "Neo soul lounge, neo soul lounge\n"
            "Lost me a little to find me now\n\n"
            "[Outro]\n"
            "One more song, one more song"
        ),
        "suno_weirdness": 38,
        "suno_style_influence": 52,
        "intro_fade_sec": 3,
        "outro_fade_sec": 4,
        "short_start": 18,
        "scenes": [
            ("Wide establishing shot: dark jazz lounge, low candlelight, velvet booths, smoke and silhouettes, cinematic 4K", 2),
            ("Slow travel over the bar: half-finished red wine glasses, vinyl spinning behind bartender, warm amber light, cinematic 4K", 2),
            ("Medium shot: woman in slip dress at lounge mic, eyes closed, gold hoop earrings, ultra detailed 4K", 2),
            ("Close-up: lipstick mark on rim of wine glass, candle flame reflection, macro cinematic 4K", 1),
            ("Medium shot: rhodes piano keys lit by single warm spotlight, smoke curling above, cinematic 4K", 2),
            ("Wide final: lounge from balcony view, audience scattered in shadow, singer at center, intimate, 4K stunning", 2),
        ],
    },

    # ── 25/35 — 23:16 — Delta Sleep Binaural (deep sleep instrumental) ──────
    {
        "slug": "delta-sleep-binaural-2026",
        "category": "activity",
        "activity_type": "meditation",
        "title": "💤 Delta Sleep Binaural — 432Hz Deep Rest 2026 | Assirem Music PROD",
        "description": (
            "Slip past the surface and into the deepest version of sleep. 💤\n\n"
            "Binaural delta waves at 432Hz — engineered for your brain to drop "
            "into restorative deep sleep within minutes.\n\n"
            "⏱️ Chapters:\n"
            "00:00 — Settling\n10:00 — Drift\n30:00 — Deep delta\n\n"
            "🎧 Best for: deep sleep, insomnia relief, meditation, healing\n\n"
            "#DeltaWaves #432Hz #DeepSleep #BinauralBeats #AssiremMusicProd #NoCopyright"
        ),
        "tags": [
            "delta waves", "432hz", "deep sleep", "binaural beats",
            "sleep music", "meditation", "ai music", "assirem music prod", "no copyright",
        ],
        "playlists": ["🧘 Meditation, Sleep & Wellness"],
        "suno_title": "Delta Sleep Binaural",
        "suno_style": (
            "binaural beats, delta waves 432hz, oceanic pad swell, pink noise base, "
            "deep drone, 45 BPM, theta descent, total relaxation, healing"
        ),
        "suno_exclude_styles": "trap, edm, drums, hip hop, rock, aggressive, vocals",
        "suno_vocal_gender": None,
        "suno_lyrics": "[Instrumental]",
        "suno_weirdness": 18,
        "suno_style_influence": 35,
        "intro_fade_sec": 6,
        "outro_fade_sec": 6,
        "short_start": 60,
        "scenes": [
            ("Wide establishing shot: still mountain lake under full moon, mist rising, total stillness, cinematic 4K", 1),
            ("Slow travel above clouds at night, stars reflected, pure silence visualised as drifting light, cinematic 4K", 1),
            ("Medium shot: person sleeping deeply in white sheets, soft blue moonlight on face, ultra detailed 4K", 1),
            ("Close-up: single dewdrop forming on a leaf in slow motion, total quiet, macro cinematic 4K", 1),
            ("Medium shot: bioluminescent forest at midnight, soft blue glow on moss, dreamlike, cinematic 4K", 1),
            ("Wide final: galaxy seen from a calm sea, milky way mirrored on still water, infinite peace, 4K stunning", 1),
        ],
    },

    # ═══════════════════════════════════════════════════════════════════════
    # DAY 6 — Jeudi 2026-04-30
    # ═══════════════════════════════════════════════════════════════════════

    # ── 26/35 — 08:15 — Grand Piano Dawn (classical instrumental) ───────────
    {
        "slug": "grand-piano-dawn-2026",
        "category": "trending",
        "title": "🎹 Grand Piano Dawn — Solo Classical 2026 | Assirem Music PROD",
        "description": (
            "Sunlight on the keys, the world still asleep. 🎹\n\n"
            "Solo grand piano in the spirit of Satie and Ludovico Einaudi — "
            "introspective, fragile, beautifully alone.\n\n"
            "⏱️ Chapters:\n"
            "00:00 — First note\n02:00 — Resolution\n04:00 — Quiet ending\n\n"
            "🎧 Best for: morning calm, reading, deep focus, meditation\n\n"
            "#PianoMusic #ContemporaryClassical #MorningPiano #Cinematic #AssiremMusicProd #NoCopyright"
        ),
        "tags": [
            "piano music", "contemporary classical", "morning piano", "cinematic",
            "solo piano", "meditation", "ai music", "assirem music prod", "no copyright",
        ],
        "playlists": ["🕊️ Cinematic & Orchestral", "🧘 Meditation, Sleep & Wellness"],
        "suno_title": "Grand Piano Dawn",
        "suno_style": (
            "solo grand piano, contemporary classical, impressionist, slow arpeggios, "
            "52 BPM, dawn, introspective, cathedral acoustic, satie-like, einaudi-like"
        ),
        "suno_exclude_styles": "trap, edm, drums, electronic, drill, lofi hip hop",
        "suno_vocal_gender": None,
        "suno_lyrics": "[Instrumental]",
        "suno_weirdness": 22,
        "suno_style_influence": 40,
        "intro_fade_sec": 4,
        "outro_fade_sec": 5,
        "short_start": 30,
        "scenes": [
            ("Wide establishing shot: empty cathedral at dawn, single grand piano in beam of stained glass light, cinematic 4K", 1),
            ("Slow travel along piano keys, dust motes in golden morning beam, soft polish reflection, cinematic 4K", 1),
            ("Medium shot: pianist's hands gliding gently over keys, eyes closed, peaceful focus, ultra detailed 4K", 1),
            ("Close-up: hammer striking string inside open piano in slow motion, sound visible as light, macro cinematic 4K", 1),
            ("Medium shot: empty wooden chairs in concert hall, single ray of sun across stage, cinematic 4K", 1),
            ("Wide final: cathedral filling with warm morning light, piano alone in center, fragile beauty, 4K stunning", 1),
        ],
    },

    # ── 27/35 — 12:10 — Kingston Riddim (reggae male vocals) ────────────────
    {
        "slug": "kingston-riddim-reggae-2026",
        "category": "trending",
        "title": "🇯🇲 Kingston Riddim — Reggae Sunshine 2026 | Assirem Music PROD",
        "description": (
            "One drop, blue sky, no worries — Jamaica in your earbuds. 🇯🇲\n\n"
            "Pure Kingston riddim with a positive male voice and golden Caribbean "
            "sunshine for your Thursday lunch.\n\n"
            "⏱️ Chapters:\n"
            "00:00 — Kingston morning\n01:20 — Chorus\n03:00 — Melodica solo\n\n"
            "🎧 Best for: lunch chill, summer vibes, reggae fans, positive mood\n\n"
            "#ReggaeMusic #Kingston #JamaicanMusic #PositiveVibes #AssiremMusicProd #NoCopyright"
        ),
        "tags": [
            "reggae music", "kingston", "jamaican music", "positive vibes",
            "one drop reggae", "summer vibes", "ai music", "assirem music prod", "no copyright",
        ],
        "playlists": ["🌶️ Latin, Caribbean & Reggae"],
        "suno_title": "Kingston Riddim",
        "suno_style": (
            "reggae one drop, dancehall lite, fender rhodes skank, bubbling bass, "
            "melodica solo, 76 BPM, kingston vibes, sunshine, positive vibrations, male voice"
        ),
        "suno_exclude_styles": "trap, drill, edm, country, heavy metal, aggressive",
        "suno_vocal_gender": "male",
        "suno_lyrics": (
            "[Verse 1]\n"
            "Sun come up over Kingston town\n"
            "Fishermen smile and the boats float down\n"
            "Saltwater breeze on Hellshire sand\n"
            "Bredren passing me a cold soda can\n\n"
            "[Pre-Chorus]\n"
            "No stress no pressure for I and I\n"
            "Just a riddim and a Caribbean sky\n\n"
            "[Chorus]\n"
            "Kingston riddim, Kingston riddim\n"
            "Music flowing like the river within\n"
            "Kingston riddim, Kingston riddim\n"
            "Every heartbeat say it's time to begin\n\n"
            "[Verse 2]\n"
            "Mama cooking ackee on the stove\n"
            "Birds flying low from a mango grove\n"
            "Ya don't gotta have plenty to feel rich\n"
            "Got the bassline pulling like a sweet itch\n\n"
            "[Chorus]\n"
            "Kingston riddim, Kingston riddim\n"
            "Music flowing like the river within\n"
            "Kingston riddim, Kingston riddim\n"
            "Every heartbeat say it's time to begin\n\n"
            "[Outro]\n"
            "One love, one heart, one riddim"
        ),
        "suno_weirdness": 28,
        "suno_style_influence": 50,
        "intro_fade_sec": 2,
        "outro_fade_sec": 3,
        "short_start": 12,
        "scenes": [
            ("Wide establishing shot: Kingston bay at noon, turquoise water, fishing boats, palm trees, blue mountains, cinematic 4K", 3),
            ("Slow travel: Hellshire beach with painted shacks, rastafari flags, kids playing, warm sunshine, cinematic 4K", 3),
            ("Medium shot: rasta singer on porch with guitar, dreadlocks, big smile, hibiscus flowers around, ultra detailed 4K", 3),
            ("Close-up: hand strumming on melodica, sunlight through palm leaves, golden glints, macro cinematic 4K", 2),
            ("Medium shot: friends on rooftop dancing slow reggae step, sunset over Kingston, cinematic 4K", 4),
            ("Wide final: Jamaican sunset over the bay, silhouettes of fishermen returning, paradise, 4K stunning", 2),
        ],
    },

    # ── 28/35 — 16:13 — Hustle Hard Drill (UK drill male vocals) ────────────
    {
        "slug": "hustle-hard-drill-2026",
        "category": "activity",
        "activity_type": "gym",
        "title": "🔥 Hustle Hard — UK Drill Workout 2026 | Assirem Music PROD",
        "description": (
            "Built different. Move different. 🔥\n\n"
            "UK drill with melodic trap drums and a male voice that doesn't ask "
            "for permission. For the gym, the grind, the chase.\n\n"
            "⏱️ Chapters:\n"
            "00:00 — Lock in\n00:50 — First verse\n02:00 — Drop\n\n"
            "🎧 Best for: workout, motivation, hustle, drill fans\n\n"
            "#UKDrill #HustleMusic #WorkoutMusic #Drill #AssiremMusicProd #NoCopyright #2026"
        ),
        "tags": [
            "uk drill", "hustle music", "workout music", "drill",
            "trap beats", "gym music", "ai music", "assirem music prod", "no copyright",
        ],
        "playlists": ["🎤 Hip-Hop, Rap & R&B", "💪 Workout, Gym & Motivation"],
        "suno_title": "Hustle Hard",
        "suno_style": (
            "uk drill, melodic trap, aggressive 808, menacing strings, "
            "hi-hat drill pattern, 142 BPM, street hustle, determination, grit, male voice"
        ),
        "suno_exclude_styles": "lofi, ambient, classical, country, soft pop, jazz",
        "suno_vocal_gender": "male",
        "suno_lyrics": (
            "[Intro]\n"
            "Yeah yeah, it's Assirem\n"
            "Hustle hard, hustle hard\n\n"
            "[Verse 1]\n"
            "Up at five 'fore the city even wake\n"
            "Black coffee and a vision I'ma make\n"
            "Doubters whisper but they fade in the back\n"
            "Every step a counter to a wack attack\n"
            "Gym is open, mind is locked\n"
            "Iron heavier than what they thought\n"
            "I don't run, the schedule run\n"
            "Sleep when the work is fully done\n\n"
            "[Chorus]\n"
            "Hustle hard, hustle hard\n"
            "Built it from a folded card\n"
            "Hustle hard, hustle hard\n"
            "Pressure made me what I are\n\n"
            "[Verse 2]\n"
            "Pen up, pad up, plate up, pray\n"
            "Money come slow but I move it like a wave\n"
            "Real ones know the hours that I gave\n"
            "Future bright like flash from a rave\n\n"
            "[Chorus]\n"
            "Hustle hard, hustle hard\n"
            "Built it from a folded card\n"
            "Hustle hard, hustle hard\n"
            "Pressure made me what I are\n\n"
            "[Outro]\n"
            "Hustle hard, no off day"
        ),
        "suno_weirdness": 48,
        "suno_style_influence": 58,
        "intro_fade_sec": 1,
        "outro_fade_sec": 2,
        "short_start": 5,
        "scenes": [
            ("Wide establishing shot: London estate at dawn, mist over concrete blocks, lone figure jogging, cinematic 4K", 3),
            ("Slow travel through underground gym at 5 AM, single overhead light, lifter chalking up, cinematic 4K", 4),
            ("Medium shot: young Black artist in hoodie spitting bars in studio, mic in hand, intensity, ultra detailed 4K", 3),
            ("Close-up: knuckles wrapped in athletic tape gripping pull-up bar, sweat dripping, macro cinematic 4K", 2),
            ("Medium shot: artist on rooftop overlooking London skyline at sunrise, hood up, arms wide, cinematic 4K", 4),
            ("Wide final: London city at dawn with crane lights flickering, lone figure walking forward, 4K stunning", 2),
        ],
    },

    # ── 29/35 — 20:02 — Velvet Night PluggnB (dark R&B female vocals) ───────
    {
        "slug": "velvet-night-pluggnb-2026",
        "category": "trending",
        "title": "🌹 Velvet Night — Dark PluggnB R&B 2026 | Assirem Music PROD",
        "description": (
            "Silk sheets, black velvet, and a heart that won't behave. 🌹\n\n"
            "PluggnB at its most luxurious — breathy female vocals over slow 808s "
            "and the kind of melody that lingers.\n\n"
            "⏱️ Chapters:\n"
            "00:00 — Velvet curtain\n01:15 — Chorus\n03:00 — Bridge confession\n\n"
            "🎧 Best for: late evening, intimate playlists, dark R&B fans\n\n"
            "#PluggnB #DarkRnB #VelvetMusic #LuxuryRnB #AssiremMusicProd #NoCopyright"
        ),
        "tags": [
            "pluggnb", "dark rnb", "velvet music", "luxury rnb",
            "moody vibes", "808 bass", "ai music", "assirem music prod", "no copyright",
        ],
        "playlists": ["🌘 Dark Vibes & Night Drive", "🎤 Hip-Hop, Rap & R&B"],
        "suno_title": "Velvet Night",
        "suno_style": (
            "pluggnb, dark r&b, atmospheric trap, breathy female vocals, 808 sub bass, "
            "shimmering synths, 130 BPM, sensual, midnight, luxury dark"
        ),
        "suno_exclude_styles": "country, edm, drill, happy pop, acoustic folk, classical",
        "suno_vocal_gender": "female",
        "suno_lyrics": (
            "[Verse 1]\n"
            "Velvet curtain, dim light low\n"
            "Tell me everything you don't want to know\n"
            "Whisper softer than the silk on skin\n"
            "Hold me darker than the place we've been\n\n"
            "[Pre-Chorus]\n"
            "Black coffee in the moonlight\n"
            "Truth tastes better after midnight\n\n"
            "[Chorus]\n"
            "Velvet night, velvet night\n"
            "Burn the bridges before sunlight\n"
            "Velvet night, velvet night\n"
            "Wrong feels so right tonight\n\n"
            "[Verse 2]\n"
            "Diamond on a dangerous chain\n"
            "Sweet temptation tasting like rain\n"
            "Skylines bleeding through the blinds\n"
            "Body forgets but the soul still finds\n\n"
            "[Chorus]\n"
            "Velvet night, velvet night\n"
            "Burn the bridges before sunlight\n"
            "Velvet night, velvet night\n"
            "Wrong feels so right tonight\n\n"
            "[Outro]\n"
            "Stay till morning, stay till morning"
        ),
        "suno_weirdness": 42,
        "suno_style_influence": 56,
        "intro_fade_sec": 2,
        "outro_fade_sec": 3,
        "short_start": 20,
        "scenes": [
            ("Wide establishing shot: luxury hotel suite at night, velvet curtains, city neon through window, cinematic 4K", 2),
            ("Slow travel along satin bedsheet, candle flickering, half-empty wine glass, intimate, cinematic 4K", 1),
            ("Medium shot: woman in black silk slip dress at floor-to-ceiling window, city behind her, ultra detailed 4K", 2),
            ("Close-up: hand sliding along velvet curtain, ring catching neon light, macro cinematic 4K", 1),
            ("Medium shot: woman lying on bed wearing pearl earrings, soft purple light, dreamy mood, cinematic 4K", 1),
            ("Wide final: floor-to-ceiling window view of midnight city, single silhouette, mysterious beauty, 4K stunning", 2),
        ],
    },

    # ── 30/35 — 23:16 — Forest Rain Sleep (nature ambient instrumental) ─────
    {
        "slug": "forest-rain-sleep-2026",
        "category": "activity",
        "activity_type": "meditation",
        "title": "🌲 Forest Rain Sleep — Nature ASMR 2026 | Assirem Music PROD",
        "description": (
            "Rain through pine needles, distant thunder, your slowest breath. 🌲\n\n"
            "Pure forest rain ambient — engineered to drop you into deep sleep "
            "by minute three. No drums, no melody, just nature.\n\n"
            "⏱️ Chapters:\n"
            "00:00 — First drops\n10:00 — Steady rain\n45:00 — Distant thunder\n\n"
            "🎧 Best for: deep sleep, ASMR, focus, anxiety relief\n\n"
            "#ForestRain #SleepMusic #NatureASMR #RainSounds #AssiremMusicProd #NoCopyright"
        ),
        "tags": [
            "forest rain", "sleep music", "nature asmr", "rain sounds",
            "ambient", "relaxation", "ai music", "assirem music prod", "no copyright",
        ],
        "playlists": ["🧘 Meditation, Sleep & Wellness"],
        "suno_title": "Forest Rain Sleep",
        "suno_style": (
            "nature ambient, forest rain, binaural, soft thunder distant, "
            "cricket ambiance, gentle stream, 40 BPM, deep sleep ASMR, total relaxation"
        ),
        "suno_exclude_styles": "drums, vocals, electronic, melody, beat, percussion",
        "suno_vocal_gender": None,
        "suno_lyrics": "[Instrumental]",
        "suno_weirdness": 15,
        "suno_style_influence": 32,
        "intro_fade_sec": 6,
        "outro_fade_sec": 6,
        "short_start": 60,
        "scenes": [
            ("Wide establishing shot: dense pine forest in the rain, mist between trees, cool blue tone, cinematic 4K", 1),
            ("Slow travel along forest stream, water flowing over moss-covered stones, soft rainfall, cinematic 4K", 1),
            ("Medium shot: ferns and pine needles dripping, droplets falling in slow motion, lush green, ultra detailed 4K", 1),
            ("Close-up: single raindrop sliding down a pine needle, perfect focus, macro cinematic 4K", 1),
            ("Medium shot: small wooden cabin in distance with warm window light, rain falling all around, cinematic 4K", 1),
            ("Wide final: aerial pull-back from forest in rain, endless green canopy, soft mist rising, 4K stunning", 1),
        ],
    },

    # ═══════════════════════════════════════════════════════════════════════
    # DAY 7 — Vendredi 2026-05-01
    # ═══════════════════════════════════════════════════════════════════════

    # ── 31/35 — 08:15 — Sunday Morning Lofi (acoustic, male vocals) ─────────
    {
        "slug": "sunday-morning-lofi-2026",
        "category": "activity",
        "activity_type": "focus",
        "title": "☁️ Sunday Morning — Acoustic Lofi 2026 | Assirem Music PROD",
        "description": (
            "Soft Sunday vibes — old t-shirt, open window, no plans. ☁️\n\n"
            "Acoustic lofi with a gentle male voice for the slowest morning of "
            "the week. Just breathe.\n\n"
            "⏱️ Chapters:\n"
            "00:00 — Window open\n01:20 — Chorus\n03:00 — Quiet bridge\n\n"
            "🎧 Best for: slow mornings, study, café vibes, gentle wake-ups\n\n"
            "#LofiAcoustic #SundayMorning #ChillMusic #IndieFolk #AssiremMusicProd #NoCopyright"
        ),
        "tags": [
            "lofi acoustic", "sunday morning", "chill music", "indie folk",
            "soft vocals", "ai music", "assirem music prod", "no copyright", "2026",
        ],
        "playlists": ["📚 Focus, Lo-Fi & Coffee Work", "🌸 Pop, Chill & Indie Rock"],
        "suno_title": "Sunday Morning",
        "suno_style": (
            "lofi acoustic, indie folk, fingerpicked guitar, brushed drums, "
            "warm pads, 70 BPM, sunday morning, gentle, soft male vocals, intimate"
        ),
        "suno_exclude_styles": "trap, edm, drill, aggressive, country, heavy metal",
        "suno_vocal_gender": "male",
        "suno_lyrics": (
            "[Verse 1]\n"
            "Sunlight slipping through the curtain crack\n"
            "Coffee steam, my old guitar in back\n"
            "Phone is silent, world can wait outside\n"
            "Sunday morning's on my side\n\n"
            "[Pre-Chorus]\n"
            "Take it slow, take it easy\n"
            "Nothing on this Sunday's leaving\n\n"
            "[Chorus]\n"
            "Sunday morning, soft and slow\n"
            "Nothing's broken, nothing to know\n"
            "Just the birds and the radio\n"
            "Sunday morning, soft and slow\n\n"
            "[Verse 2]\n"
            "Pancakes burning just a little dark\n"
            "Cat is yawning in a sunlight park\n"
            "Letters left unread on the table side\n"
            "Sunday morning's a quiet ride\n\n"
            "[Chorus]\n"
            "Sunday morning, soft and slow\n"
            "Nothing's broken, nothing to know\n"
            "Just the birds and the radio\n"
            "Sunday morning, soft and slow\n\n"
            "[Outro]\n"
            "Let the morning be the morning"
        ),
        "suno_weirdness": 22,
        "suno_style_influence": 42,
        "intro_fade_sec": 3,
        "outro_fade_sec": 4,
        "short_start": 14,
        "scenes": [
            ("Wide establishing shot: cozy living room on Sunday morning, sunlight pouring through curtain, plants, vinyl, cinematic 4K", 1),
            ("Slow pan: kitchen counter with coffee press, half-eaten pancake, open notebook, warm light, cinematic 4K", 1),
            ("Medium shot: young man in white tee strumming acoustic guitar by window, eyes half-closed, ultra detailed 4K", 2),
            ("Close-up: fingers picking acoustic guitar strings, sunlight on wood grain, dust motes, macro cinematic 4K", 1),
            ("Medium shot: cat curled on windowsill, breeze in lace curtain, soft pastel sky, cinematic 4K", 1),
            ("Wide final: open balcony view over peaceful neighborhood, leaves moving in breeze, perfect calm, 4K stunning", 1),
        ],
    },

    # ── 32/35 — 12:10 — Hanoi Silk Road (Vietnamese world instrumental) ─────
    {
        "slug": "hanoi-silk-road-2026",
        "category": "world_music",
        "country": "Vietnam",
        "country_flag": "🇻🇳",
        "title": "🇻🇳 Hanoi Silk Road — Vietnamese Traditional 2026 | Assirem Music PROD",
        "description": (
            "Lanterns in old Hanoi, đàn tranh strings drifting on the morning breeze. 🇻🇳\n\n"
            "Traditional Vietnamese instruments arranged for modern listeners — silk "
            "road serenity for your Friday lunch.\n\n"
            "⏱️ Chapters:\n"
            "00:00 — Old quarter awakens\n02:00 — Tea ceremony\n04:00 — Riverside drift\n\n"
            "🎧 Best for: world music discovery, meditation, focus, cultural travel\n\n"
            "#VietnameseMusic #WorldMusic #SilkRoad #Hanoi #AssiremMusicProd #NoCopyright"
        ),
        "tags": [
            "vietnamese music", "world music", "silk road", "hanoi",
            "asian traditional", "đàn tranh", "ai music", "assirem music prod", "no copyright",
        ],
        "playlists": ["🌏 World Music"],
        "suno_title": "Hanoi Silk Road",
        "suno_style": (
            "vietnamese traditional, đàn tranh zither, đàn nguyệt moon lute, "
            "bamboo flute, pentatonic scale, ceremonial, 70 BPM, silk road, eastern serenity"
        ),
        "suno_exclude_styles": "edm, trap, drill, western pop, heavy drums, electronic",
        "suno_vocal_gender": None,
        "suno_lyrics": "[Instrumental]",
        "suno_weirdness": 32,
        "suno_style_influence": 48,
        "intro_fade_sec": 4,
        "outro_fade_sec": 4,
        "short_start": 28,
        "scenes": [
            ("Wide establishing shot: old quarter Hanoi at noon, red and yellow lanterns above narrow streets, scooters and silk shops, cinematic 4K", 3),
            ("Slow travel along Hoàn Kiếm lake, weeping willows, traditional pagoda reflected in water, cinematic 4K", 2),
            ("Medium shot: Vietnamese woman in white áo dài playing đàn tranh in tea garden, silk flowing, ultra detailed 4K", 2),
            ("Close-up: fingertips plucking đàn tranh strings, lacquer wood and mother-of-pearl inlay, macro cinematic 4K", 2),
            ("Medium shot: tea ceremony on lacquered low table, steaming cups, bamboo blinds filtering sun, cinematic 4K", 2),
            ("Wide final: rice terraces of Sapa northern Vietnam, mist over silk-green fields, eternal beauty, 4K stunning", 2),
        ],
    },

    # ── 33/35 — 16:13 — Amapiano Summer (afrofuturism instrumental) ─────────
    {
        "slug": "amapiano-summer-2026",
        "category": "trending",
        "title": "🌞 Amapiano Summer — Afro Dance 2026 | Assirem Music PROD",
        "description": (
            "Joburg log drums hit different in summer. 🌞\n\n"
            "Pure amapiano — South African shuffle, deep piano keys, log drum bass "
            "and unstoppable rhythm. Lock in.\n\n"
            "⏱️ Chapters:\n"
            "00:00 — Township opens\n01:00 — The shuffle\n03:00 — Log drum drop\n\n"
            "🎧 Best for: dancing, sunny afternoons, afrobeat fans, summer\n\n"
            "#Amapiano #AfroBeats #SouthAfrica #DanceMusic #AssiremMusicProd #NoCopyright #2026"
        ),
        "tags": [
            "amapiano", "afrobeats", "south africa", "dance music",
            "log drum", "afro electronic", "ai music", "assirem music prod", "no copyright",
        ],
        "playlists": ["🌍 Afrofuturism", "🌶️ Latin, Caribbean & Reggae"],
        "suno_title": "Amapiano Summer",
        "suno_style": (
            "amapiano, afrobeats, log drum bass, piano keys pattern, "
            "deep sub synth, township shuffle, 112 BPM, south african, dance, euphoric, sunny"
        ),
        "suno_exclude_styles": "lofi, country, classical, sad ballad, polka, drone",
        "suno_vocal_gender": None,
        "suno_lyrics": "[Instrumental]",
        "suno_weirdness": 38,
        "suno_style_influence": 55,
        "intro_fade_sec": 1,
        "outro_fade_sec": 3,
        "short_start": 8,
        "scenes": [
            ("Wide establishing shot: Soweto street party at noon, people dancing, vibrant murals, sunshine, cinematic 4K", 4),
            ("Slow travel through Joburg rooftop in afternoon haze, dancers in colorful outfits, golden light, cinematic 4K", 4),
            ("Medium shot: South African dancer doing the amapiano shuffle, full motion blur on legs, ultra detailed 4K", 6),
            ("Close-up: hand on midi keyboard playing piano riff, sweat and sun glints on skin, macro cinematic 4K", 3),
            ("Medium shot: festival crowd at sunset, dust kicked up, hands raised, pure joy, cinematic 4K", 5),
            ("Wide final: aerial of Joburg skyline at golden hour, festival lights starting up, summer vibe, 4K stunning", 3),
        ],
    },

    # ── 34/35 — 20:02 — Space Odyssey Epic (cinematic with choir) ───────────
    {
        "slug": "space-odyssey-epic-2026",
        "category": "trending",
        "title": "🚀 Space Odyssey — Epic Orchestral Choir 2026 | Assirem Music PROD",
        "description": (
            "When humanity reaches the stars — let it sound like this. 🚀\n\n"
            "Full orchestra with epic choir, in the cinematic spirit of Hans Zimmer "
            "and Vangelis. For evenings that feel like history.\n\n"
            "⏱️ Chapters:\n"
            "00:00 — Liftoff\n01:30 — Beyond Earth\n04:00 — First contact\n\n"
            "🎧 Best for: cinematic playlists, focus, epic moods, space fans\n\n"
            "#EpicOrchestral #SpaceMusic #FilmScore #Cinematic #AssiremMusicProd #NoCopyright"
        ),
        "tags": [
            "epic orchestral", "space music", "film score", "cinematic",
            "hans zimmer style", "choir epic", "ai music", "assirem music prod", "no copyright",
        ],
        "playlists": ["🕊️ Cinematic & Orchestral"],
        "suno_title": "Space Odyssey",
        "suno_style": (
            "epic orchestral, space opera, full symphony, soaring choir, taikos, "
            "60 BPM, hans zimmer influence, cosmic, emotional climax, cinematic"
        ),
        "suno_exclude_styles": "trap, lofi, edm, country, drill, pop, electronic dance",
        "suno_vocal_gender": None,
        "suno_lyrics": "[Instrumental]",
        "suno_weirdness": 28,
        "suno_style_influence": 55,
        "intro_fade_sec": 4,
        "outro_fade_sec": 5,
        "short_start": 60,
        "scenes": [
            ("Wide establishing shot: massive rocket on launchpad at sunset, steam billowing, gantry lights, cinematic 4K", 3),
            ("Slow travel: rocket lifting off in slow motion, fire trails arcing, Earth curving below, cinematic 4K", 4),
            ("Medium shot: astronaut helmet visor reflecting Earth from low orbit, single tear visible, ultra detailed 4K", 2),
            ("Close-up: spacecraft window with Saturn rings filling frame, light dancing across glass, macro cinematic 4K", 2),
            ("Medium shot: lone explorer planting flag on alien red planet, two suns setting behind, cinematic 4K", 3),
            ("Wide final: galaxy spiral arm seen from spacecraft, infinite stars, scale of the universe, 4K stunning", 2),
        ],
    },

    # ── 35/35 — 23:16 — Theta Dreams 396Hz (deep sleep instrumental) ────────
    {
        "slug": "theta-dreams-396hz-2026",
        "category": "activity",
        "activity_type": "meditation",
        "title": "🌌 Theta Dreams — 396Hz Liberation Sleep 2026 | Assirem Music PROD",
        "description": (
            "Drift past the body and into the dream itself. 🌌\n\n"
            "396Hz liberation frequency over deep theta wave drone — engineered "
            "to release fear and guide you into healing dream sleep.\n\n"
            "⏱️ Chapters:\n"
            "00:00 — Surrender\n10:00 — Theta state\n40:00 — Healing dreams\n\n"
            "🎧 Best for: deep sleep, dream work, healing, anxiety release\n\n"
            "#ThetaWaves #396Hz #SleepHealing #DreamMusic #AssiremMusicProd #NoCopyright"
        ),
        "tags": [
            "theta waves", "396hz", "sleep healing", "dream music",
            "binaural sleep", "meditation", "ai music", "assirem music prod", "no copyright",
        ],
        "playlists": ["🧘 Meditation, Sleep & Wellness"],
        "suno_title": "Theta Dreams 396Hz",
        "suno_style": (
            "deep sleep, theta waves, 396hz liberation frequency, subconscious drift, "
            "whale song fragments, zero percussion, 35 BPM, dreamstate, healing"
        ),
        "suno_exclude_styles": "drums, vocals, beat, percussion, rhythm, melody, electronic",
        "suno_vocal_gender": None,
        "suno_lyrics": "[Instrumental]",
        "suno_weirdness": 16,
        "suno_style_influence": 30,
        "intro_fade_sec": 7,
        "outro_fade_sec": 7,
        "short_start": 90,
        "scenes": [
            ("Wide establishing shot: deep ocean at night, moonlight on surface, infinite calm, cinematic 4K", 1),
            ("Slow travel: bioluminescent jellyfish floating in dark water, soft blue glow, cinematic 4K", 1),
            ("Medium shot: peaceful sleeper under starlit ceiling projection, deep dream state, ultra detailed 4K", 1),
            ("Close-up: water surface ripples in slow motion, moonlight scattered, macro cinematic 4K", 1),
            ("Medium shot: floating astronaut in zero gravity, eyes closed, perfect peace, cinematic 4K", 1),
            ("Wide final: galaxy spiral over still ocean, mirror reflection, dream vastness, 4K stunning", 1),
        ],
    },

]
