CREATE TABLE IF NOT EXISTS search_configs (
    id          SERIAL PRIMARY KEY,
    platform    TEXT NOT NULL,
    search_type TEXT NOT NULL,
    value       TEXT NOT NULL,
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    source      TEXT NOT NULL DEFAULT 'manual',
    tags        TEXT NOT NULL DEFAULT '[]',
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(platform, search_type, value)
);

CREATE TABLE IF NOT EXISTS creators (
    id                   SERIAL PRIMARY KEY,
    platform             TEXT NOT NULL,
    username             TEXT NOT NULL,
    display_name         TEXT,
    bio                  TEXT,
    link_in_bio          TEXT,
    followers            INTEGER,
    following            INTEGER,
    total_posts          INTEGER,
    verified             BOOLEAN,
    business_account     BOOLEAN,
    is_private           BOOLEAN,
    profile_pic_url      TEXT,
    email                TEXT,
    category             TEXT,
    location             TEXT,
    niche                TEXT,
    ai_filter_pass       BOOLEAN,
    ai_filter_reason     TEXT,
    epic_trip_score      DOUBLE PRECISION,
    score_engagement     DOUBLE PRECISION,
    score_niche          DOUBLE PRECISION,
    score_followers      DOUBLE PRECISION,
    score_growth         DOUBLE PRECISION,
    score_activity       DOUBLE PRECISION,
    avg_engagement       DOUBLE PRECISION,
    posts_last_30_days   INTEGER,
    posting_frequency    DOUBLE PRECISION,
    is_active            BOOLEAN,
    discovered_via_type  TEXT,
    discovered_via_value TEXT,
    status               TEXT DEFAULT 'discovered',
    is_lead              BOOLEAN NOT NULL DEFAULT FALSE,
    first_seen_at        TIMESTAMPTZ DEFAULT NOW(),
    last_updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(platform, username)
);

CREATE TABLE IF NOT EXISTS posts (
    id              SERIAL PRIMARY KEY,
    creator_id      INTEGER NOT NULL REFERENCES creators(id) ON DELETE CASCADE,
    platform        TEXT NOT NULL,
    post_id         TEXT NOT NULL,
    post_type       TEXT,
    post_url        TEXT,
    published_at    TIMESTAMPTZ,
    likes           INTEGER,
    comments        INTEGER,
    shares          INTEGER,
    views           INTEGER,
    engagement_rate DOUBLE PRECISION,
    caption         TEXT,
    hashtags        TEXT,
    UNIQUE(platform, post_id)
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id                  SERIAL PRIMARY KEY,
    platform            TEXT,
    seeds_used          TEXT,
    creators_found      INTEGER,
    creators_qualified  INTEGER,
    apify_cost_usd      DOUBLE PRECISION,
    openai_cost_usd     DOUBLE PRECISION,
    started_at          TIMESTAMPTZ,
    finished_at         TIMESTAMPTZ,
    status              TEXT DEFAULT 'running',
    error_message       TEXT
);

CREATE TABLE IF NOT EXISTS score_history (
    id              SERIAL PRIMARY KEY,
    creator_id      INTEGER NOT NULL REFERENCES creators(id) ON DELETE CASCADE,
    run_id          INTEGER REFERENCES pipeline_runs(id) ON DELETE SET NULL,
    epic_trip_score DOUBLE PRECISION,
    followers       INTEGER,
    avg_engagement  DOUBLE PRECISION,
    scored_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS outreach (
    id           SERIAL PRIMARY KEY,
    creator_id   INTEGER NOT NULL REFERENCES creators(id) ON DELETE CASCADE,
    contacted_at TIMESTAMPTZ,
    channel      TEXT,
    status       TEXT,
    notes        TEXT
);
