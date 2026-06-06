CREATE TABLE IF NOT EXISTS sites (
    id BIGSERIAL PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,
    normalized_url TEXT NOT NULL UNIQUE,
    onion_host TEXT,
    title TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    content_text TEXT NOT NULL DEFAULT '',
    keywords TEXT[] NOT NULL DEFAULT '{}',
    language TEXT NOT NULL DEFAULT 'unknown',
    warning_labels TEXT[] NOT NULL DEFAULT '{}',
    content_hash TEXT NOT NULL DEFAULT '',
    http_status INTEGER,
    first_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    indexed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS crawl_frontier (
    id BIGSERIAL PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,
    normalized_url TEXT NOT NULL UNIQUE,
    onion_host TEXT,
    discovered_from TEXT,
    depth INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'queued',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sites_url ON sites (url);
CREATE INDEX IF NOT EXISTS idx_sites_onion_host ON sites (onion_host);
CREATE INDEX IF NOT EXISTS idx_sites_last_seen ON sites (last_seen DESC);
CREATE INDEX IF NOT EXISTS idx_frontier_status_next ON crawl_frontier (status, next_attempt_at, id);
CREATE INDEX IF NOT EXISTS idx_frontier_depth ON crawl_frontier (depth);
CREATE INDEX IF NOT EXISTS idx_frontier_onion_host_status ON crawl_frontier (onion_host, status);
