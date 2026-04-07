-- ═══════════════════════════════════════════════════════
--  SWARMGRAPH DATABASE — Pro-Grade Schema v1.0
--  Swarm & Bee LLC — Defendable AI Intelligence
--
--  Every table maps to a SwarmGraph node or edge type.
--  Real-time alignment with the context graph.
-- ═══════════════════════════════════════════════════════

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";       -- pgvector for future embedding search

-- ─── DOMAINS ─────────────────────────────────────────
CREATE TABLE domains (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    description     TEXT,
    pair_count      BIGINT DEFAULT 0,
    deed_count      BIGINT DEFAULT 0,
    rj_count        BIGINT DEFAULT 0,
    rj_yield        REAL DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO domains (id, name, description) VALUES
    ('medical',  'Medical',  '61 specialties — internal medicine, surgery, neurology, pharmacology...'),
    ('cre',      'CRE',      'Commercial Real Estate — underwriting, analysis, compliance'),
    ('aviation', 'Aviation', 'A&P/IA maintenance engineering, airworthiness, inspection'),
    ('grants',   'Grants',   'Federal grants, SBA loans, tax credits, SBIR/STTR');

-- ─── JUDGES ──────────────────────────────────────────
CREATE TABLE judges (
    id              TEXT PRIMARY KEY,
    model           TEXT NOT NULL,
    label           TEXT NOT NULL,
    modified        BOOLEAN DEFAULT FALSE,
    deterministic   BOOLEAN DEFAULT TRUE,
    total_scores    BIGINT DEFAULT 0,
    mean_score      REAL,
    calibration_drift REAL DEFAULT 0,
    last_calibrated TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO judges (id, model, label) VALUES
    ('gemma-4-e2b',  'google/gemma-4-E2B-it', 'gemma-4-e2b'),
    ('qwen-2.5-9b',  'Qwen/Qwen2.5-9B',      'qwen-2.5-9b');

-- ─── SILICON ─────────────────────────────────────────
CREATE TABLE silicon (
    id              TEXT PRIMARY KEY,
    hardware        TEXT NOT NULL,
    arch            TEXT NOT NULL,
    power_watts     INTEGER,
    vram_gb         REAL,
    location        TEXT DEFAULT 'datacenter',
    ip_address      TEXT,
    status          TEXT DEFAULT 'online',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO silicon (id, hardware, arch, power_watts, vram_gb, location, ip_address) VALUES
    ('swarmrails-gpu0', 'NVIDIA RTX PRO 6000 Blackwell', 'Blackwell', 300, 96, 'datacenter', 'localhost'),
    ('swarmrails-gpu1', 'NVIDIA RTX PRO 6000 Blackwell', 'Blackwell', 300, 96, 'datacenter', 'localhost'),
    ('whale-gpu0',      'NVIDIA RTX 3090',               'Ampere',    350, 24, 'datacenter', '192.168.0.99'),
    ('jetson-sigedge',  'NVIDIA Jetson Orin Nano',        'Ampere',      6,  8, 'edge',       '192.168.0.79'),
    ('zima-t1000',      'NVIDIA T1000',                   'Turing',     50,  4, 'edge',       '192.168.0.230');

-- ─── WRITERS ─────────────────────────────────────────
CREATE TABLE writers (
    id              TEXT PRIMARY KEY,
    base_model      TEXT NOT NULL,
    model_name      TEXT NOT NULL,
    status          TEXT DEFAULT 'cooking',    -- cooking, complete, deployed
    trained_on_count BIGINT DEFAULT 0,
    eval_loss       REAL,
    train_hours     REAL,
    peak_vram_gb    REAL,
    silicon_id      TEXT REFERENCES silicon(id),
    lora_r          INTEGER,
    lora_alpha      INTEGER,
    learning_rate   REAL,
    epochs          INTEGER,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);

INSERT INTO writers (id, base_model, model_name, status, silicon_id, lora_r, lora_alpha, learning_rate, epochs) VALUES
    ('swarmgrant-gemma4-31b', 'google/gemma-4-31B-it', 'swarmGrant-Gemma4-31B', 'cooking', 'swarmrails-gpu0', 64, 32, 1e-5, 3);

-- ─── PAIRS ───────────────────────────────────────────
CREATE TABLE pairs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    fingerprint     TEXT NOT NULL UNIQUE,
    domain_id       TEXT NOT NULL REFERENCES domains(id),
    messages        JSONB NOT NULL,
    char_count      INTEGER,
    token_count     INTEGER,
    metadata        JSONB DEFAULT '{}',
    source_file     TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_pairs_domain ON pairs(domain_id);
CREATE INDEX idx_pairs_fingerprint ON pairs(fingerprint);
CREATE INDEX idx_pairs_metadata ON pairs USING gin(metadata);

-- ─── TRIBUNAL SCORES ─────────────────────────────────
CREATE TABLE tribunal_scores (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pair_id         UUID NOT NULL REFERENCES pairs(id),
    judge_id        TEXT NOT NULL REFERENCES judges(id),
    pass_number     INTEGER NOT NULL DEFAULT 1,  -- 1 or 2 (validate the validator)
    score           REAL NOT NULL CHECK (score >= 0 AND score <= 1),
    reasoning       TEXT,
    scored_at       TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(pair_id, judge_id, pass_number)
);

CREATE INDEX idx_scores_pair ON tribunal_scores(pair_id);
CREATE INDEX idx_scores_judge ON tribunal_scores(judge_id);
CREATE INDEX idx_scores_score ON tribunal_scores(score);

-- ─── DEEDS ───────────────────────────────────────────
CREATE TABLE deeds (
    id              TEXT PRIMARY KEY,           -- SB-2026-0403-00001
    pair_id         UUID NOT NULL REFERENCES pairs(id),
    domain_id       TEXT NOT NULL REFERENCES domains(id),

    -- Proof 01: Origin
    origin_model    TEXT,
    origin_node     TEXT,
    origin_hardware TEXT,
    origin_strategy TEXT,

    -- Proof 02: Quality
    judge_a_id      TEXT REFERENCES judges(id),
    judge_a_score   REAL,
    judge_a_pass1   REAL,
    judge_a_pass2   REAL,
    judge_a_drift   REAL,
    judge_a_reasoning TEXT,
    judge_b_id      TEXT REFERENCES judges(id),
    judge_b_score   REAL,
    judge_b_pass1   REAL,
    judge_b_pass2   REAL,
    judge_b_drift   REAL,
    judge_b_reasoning TEXT,
    final_score     REAL NOT NULL CHECK (final_score >= 0 AND final_score <= 1),
    max_drift       REAL,
    validated       BOOLEAN DEFAULT TRUE,

    -- Proof 03: Process
    attempts        INTEGER DEFAULT 1,
    generation_time_ms INTEGER,
    prior_scores    REAL[],

    -- Proof 04: Economics
    energy_joules   REAL,
    cost_usd        REAL,
    cost_trend      TEXT,

    -- Proof 05: Trust
    batch_id        TEXT,
    merkle_root     TEXT,
    merkle_leaf_idx INTEGER,
    anchor_id       TEXT,

    -- Classification
    tier            TEXT NOT NULL CHECK (tier IN ('royal_jelly', 'honey', 'propolis')),
    tier_threshold  TEXT,

    -- Timestamps
    sealed_at       TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_deeds_pair ON deeds(pair_id);
CREATE INDEX idx_deeds_domain ON deeds(domain_id);
CREATE INDEX idx_deeds_tier ON deeds(tier);
CREATE INDEX idx_deeds_score ON deeds(final_score);
CREATE INDEX idx_deeds_sealed ON deeds(sealed_at);
CREATE INDEX idx_deeds_batch ON deeds(batch_id);

-- ─── BATCHES ─────────────────────────────────────────
CREATE TABLE batches (
    id              TEXT PRIMARY KEY,
    merkle_root     TEXT NOT NULL,
    leaf_count      INTEGER NOT NULL,
    block_range     TEXT,
    domain_id       TEXT REFERENCES domains(id),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─── ANCHORS ─────────────────────────────────────────
CREATE TABLE anchors (
    id              TEXT PRIMARY KEY,
    batch_id        TEXT REFERENCES batches(id),
    hedera_topic    TEXT NOT NULL DEFAULT '0.0.10291838',
    hedera_sequence INTEGER,
    hedera_timestamp TIMESTAMPTZ,
    merkle_root     TEXT NOT NULL,
    verify_url      TEXT,
    status          TEXT DEFAULT 'pending',     -- pending, submitted, confirmed
    anchored_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_anchors_batch ON anchors(batch_id);
CREATE INDEX idx_anchors_topic ON anchors(hedera_topic);

-- ─── GRAPH EDGES ─────────────────────────────────────
-- Stores all SwarmGraph relationships for traversal queries
CREATE TABLE graph_edges (
    id              BIGSERIAL PRIMARY KEY,
    source_type     TEXT NOT NULL,
    source_id       TEXT NOT NULL,
    target_type     TEXT NOT NULL,
    target_id       TEXT NOT NULL,
    edge_type       TEXT NOT NULL,
    properties      JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_edges_source ON graph_edges(source_id, edge_type);
CREATE INDEX idx_edges_target ON graph_edges(target_id, edge_type);
CREATE INDEX idx_edges_type ON graph_edges(edge_type);

-- ─── CONVERGENCE ─────────────────────────────────────
-- Time-series tracking of quality convergence per domain
CREATE TABLE convergence (
    id              BIGSERIAL PRIMARY KEY,
    domain_id       TEXT NOT NULL REFERENCES domains(id),
    window_index    INTEGER NOT NULL,
    window_size     INTEGER DEFAULT 50,
    mean_score      REAL,
    rj_count        INTEGER,
    honey_count     INTEGER,
    propolis_count  INTEGER,
    cost_per_deed   REAL,
    energy_per_deed REAL,
    measured_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_convergence_domain ON convergence(domain_id, window_index);

-- ─── CALIBRATIONS ────────────────────────────────────
-- Judge calibration snapshots over time
CREATE TABLE calibrations (
    id              BIGSERIAL PRIMARY KEY,
    judge_id        TEXT NOT NULL REFERENCES judges(id),
    window_index    INTEGER NOT NULL,
    sample_size     INTEGER,
    mean_score      REAL,
    std_dev         REAL,
    drift_from_baseline REAL,
    calibrated      BOOLEAN DEFAULT TRUE,
    measured_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_calibrations_judge ON calibrations(judge_id, window_index);

-- ─── WRITER TRAINING LOG ─────────────────────────────
CREATE TABLE training_log (
    id              BIGSERIAL PRIMARY KEY,
    writer_id       TEXT NOT NULL REFERENCES writers(id),
    step            INTEGER NOT NULL,
    train_loss      REAL,
    eval_loss       REAL,
    learning_rate   REAL,
    epoch           REAL,
    logged_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_training_writer ON training_log(writer_id, step);

-- ─── AUDIT LOG ───────────────────────────────────────
-- Every significant action is logged
CREATE TABLE audit_log (
    id              BIGSERIAL PRIMARY KEY,
    action          TEXT NOT NULL,
    entity_type     TEXT NOT NULL,
    entity_id       TEXT NOT NULL,
    details         JSONB DEFAULT '{}',
    performed_by    TEXT DEFAULT 'system',
    performed_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_audit_entity ON audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_action ON audit_log(action);
