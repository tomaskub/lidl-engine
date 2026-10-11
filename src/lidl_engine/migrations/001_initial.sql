CREATE TABLE flyers (
    id bigserial PRIMARY KEY,
    slug text NOT NULL,
    issue_year integer NOT NULL,
    title text NOT NULL,
    url text NOT NULL,
    valid_from date,
    valid_to date,
    UNIQUE (slug, issue_year)
);
CREATE TABLE selection (id boolean PRIMARY KEY DEFAULT true CHECK (id), flyer_id bigint REFERENCES flyers);
CREATE TABLE runs (
    id bigserial PRIMARY KEY,
    flyer_id bigint REFERENCES flyers,
    started_at timestamptz NOT NULL,
    deadline timestamptz NOT NULL,
    finished_at timestamptz,
    status text NOT NULL,
    expected integer NOT NULL DEFAULT 0,
    processed integer NOT NULL DEFAULT 0,
    errors jsonb NOT NULL DEFAULT '[]'
);
CREATE TABLE pages (
    id bigserial PRIMARY KEY,
    flyer_id bigint NOT NULL REFERENCES flyers,
    number integer NOT NULL CHECK (number > 0),
    url text NOT NULL,
    UNIQUE (flyer_id, number)
);
CREATE TABLE revisions (
    id bigserial PRIMARY KEY,
    page_id bigint NOT NULL REFERENCES pages,
    content_hash text NOT NULL,
    image_path text NOT NULL,
    mime_type text NOT NULL,
    observed_at timestamptz NOT NULL,
    UNIQUE (page_id, content_hash)
);
CREATE TABLE tasks (
    id bigserial PRIMARY KEY,
    revision_id bigint NOT NULL REFERENCES revisions ON DELETE CASCADE,
    stage text NOT NULL CHECK (stage IN ('description','extraction')),
    contract text NOT NULL,
    batch_id text,
    result text,
    evidence jsonb,
    UNIQUE (revision_id, stage, contract)
);
CREATE TABLE offers (
    id text PRIMARY KEY,
    conflict_key text NOT NULL,
    facts jsonb NOT NULL
);
CREATE INDEX offers_conflict_key ON offers(conflict_key);
CREATE TABLE occurrences (
    id bigserial PRIMARY KEY,
    offer_id text NOT NULL REFERENCES offers,
    revision_id bigint NOT NULL REFERENCES revisions,
    facts jsonb NOT NULL,
    active boolean NOT NULL DEFAULT true,
    observed_at timestamptz NOT NULL,
    retain_until date NOT NULL,
    UNIQUE (offer_id, revision_id)
);
CREATE INDEX occurrences_active ON occurrences(offer_id) WHERE active;
CREATE TABLE offer_categories (
    offer_id text NOT NULL REFERENCES offers ON DELETE CASCADE,
    category text NOT NULL,
    PRIMARY KEY (offer_id, category)
);
