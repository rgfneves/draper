from __future__ import annotations

# Keywords used in score_niche() — override these per experiment or via dashboard
TRAVEL_KEYWORDS: list[str] = [
    "travel", "viaje", "viajes", "viajero", "viajera", "mochilero", "mochilera",
    "backpacker", "backpacking", "traveler", "travelling", "traveling",
    "wanderlust", "adventure", "aventura", "explorer", "explorar",
    "nomad", "nomade", "roadtrip", "road trip", "wanderer",
]

PARTIAL_KEYWORDS: list[str] = [
    "content", "creator", "lifestyle", "vlog", "blog",
    "outdoor", "nature", "mundo", "world",
]

INSTAGRAM: dict = {
    "min_followers": 800,
    "max_followers": 7000,
    "min_posts_30_days": 4,
    "min_engagement": 0.00,
}

TIKTOK: dict = {
    "min_followers": 2000,
    "max_followers": 50000,
    "min_engagement": 0.005,
    "min_posting_frequency": 0.14,  # posts per day
}

EXCLUDED_KEYWORDS: list[str] = [
    "luxury", "luxury travel", "5-star hotels", "resort life", "business class",
    "private jet", "luxury experiences", "fine dining", "glam travel",
    "influencer lifestyle", "vip traveler", "fashion + travel", "bucket list luxury",
    "chill & relax", "fashion overland", "travelling with style", "premium adventure",
    "wellness retreats", "cruise life", "travelling in australia", "travelling in new zealand",
    "lujo", "fotografía de viajes de lujo", "hoteles de 5 estrellas", "vida en resorts",
    "clase ejecutiva", "jet privado", "experiencias de lujo", "alta gastronomía",
    "viajes glamorosos", "estilo de vida influencer", "viajero vip", "moda + viajes",
    "lujo de lista de deseos", "descansar y relajarse", "moda sobre ruedas",
    "moda por tierra", "viajar com estilo", "aventura premium", "retiros de bem-estar",
    "vida em cruzeiro", "viajar por australia", "viajar por nova zelândia",
    "food", "meme", "nursing", "medicine", "agency", "business",
    "photography", "fotografia",
]
