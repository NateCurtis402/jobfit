-- Runs once on an empty data volume (docker-entrypoint-initdb.d), and is also
-- safe to re-run by hand: every statement is idempotent.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS postings (
    id            BIGSERIAL PRIMARY KEY,
    source        TEXT        NOT NULL,              -- 'remotive', 'remoteok', 'adzuna', ...
    external_id   TEXT        NOT NULL,              -- the board's own id
    title         TEXT        NOT NULL,
    company       TEXT        NOT NULL,
    location      TEXT        NOT NULL DEFAULT '',
    url           TEXT        NOT NULL DEFAULT '',
    description   TEXT        NOT NULL DEFAULT '',
    tags          TEXT[]      NOT NULL DEFAULT '{}',
    posted_at     DATE,
    salary_raw    TEXT        NOT NULL DEFAULT '',
    content_hash  TEXT        NOT NULL,              -- dedupes the same job across boards
    embedding     VECTOR(768),                       -- nomic-embed-text width
    embedded_at   TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source, external_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS postings_content_hash_key ON postings (content_hash);

-- HNSW + cosine: approximate nearest neighbour, the index type pgvector
-- recommends for read-heavy search at this size.
CREATE INDEX IF NOT EXISTS postings_embedding_hnsw
    ON postings USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS postings_posted_at_idx ON postings (posted_at DESC);

-- Lexical half of hybrid retrieval. Dense vectors miss exact terms ("LLM",
-- "Kubernetes"); full-text search nails them and is free in Postgres. The
-- generated column stays in sync with the row automatically.
ALTER TABLE postings
    ADD COLUMN IF NOT EXISTS search_vector tsvector
    GENERATED ALWAYS AS (
        to_tsvector('english', coalesce(title, '') || ' ' || coalesce(description, ''))
    ) STORED;

CREATE INDEX IF NOT EXISTS postings_search_vector_idx
    ON postings USING gin (search_vector);
