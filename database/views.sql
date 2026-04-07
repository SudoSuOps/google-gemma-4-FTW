-- ═══════════════════════════════════════════════════════
--  SWARMGRAPH — Materialized Views & Functions
--  Real-time dashboard queries, pre-computed for speed
-- ═══════════════════════════════════════════════════════

-- ─── DOMAIN SUMMARY VIEW ─────────────────────────────
CREATE MATERIALIZED VIEW mv_domain_summary AS
SELECT
    d.id AS domain_id,
    d.name AS domain_name,
    COUNT(de.id) AS total_deeds,
    COUNT(de.id) FILTER (WHERE de.tier = 'royal_jelly') AS rj_count,
    COUNT(de.id) FILTER (WHERE de.tier = 'honey') AS honey_count,
    COUNT(de.id) FILTER (WHERE de.tier = 'propolis') AS propolis_count,
    ROUND(AVG(de.final_score)::numeric, 4) AS mean_score,
    ROUND(MIN(de.final_score)::numeric, 4) AS min_score,
    ROUND(MAX(de.final_score)::numeric, 4) AS max_score,
    ROUND(
        (COUNT(de.id) FILTER (WHERE de.tier = 'royal_jelly'))::numeric /
        NULLIF(COUNT(de.id), 0)::numeric, 4
    ) AS rj_yield,
    ROUND(AVG(de.cost_usd)::numeric, 6) AS avg_cost_per_deed,
    MAX(de.sealed_at) AS last_deed_at
FROM domains d
LEFT JOIN deeds de ON de.domain_id = d.id
GROUP BY d.id, d.name;

CREATE UNIQUE INDEX ON mv_domain_summary(domain_id);

-- ─── JUDGE PERFORMANCE VIEW ──────────────────────────
CREATE MATERIALIZED VIEW mv_judge_performance AS
SELECT
    j.id AS judge_id,
    j.label,
    j.model,
    COUNT(ts.id) AS total_scores,
    ROUND(AVG(ts.score)::numeric, 4) AS mean_score,
    ROUND(STDDEV(ts.score)::numeric, 4) AS score_stddev,
    ROUND(MIN(ts.score)::numeric, 4) AS min_score,
    ROUND(MAX(ts.score)::numeric, 4) AS max_score,
    COUNT(ts.id) FILTER (WHERE ts.pass_number = 1) AS pass_1_count,
    COUNT(ts.id) FILTER (WHERE ts.pass_number = 2) AS pass_2_count
FROM judges j
LEFT JOIN tribunal_scores ts ON ts.judge_id = j.id
GROUP BY j.id, j.label, j.model;

CREATE UNIQUE INDEX ON mv_judge_performance(judge_id);

-- ─── WRITER PROVENANCE VIEW ──────────────────────────
CREATE MATERIALIZED VIEW mv_writer_provenance AS
SELECT
    w.id AS writer_id,
    w.model_name,
    w.base_model,
    w.status,
    w.eval_loss,
    COUNT(DISTINCT de.id) AS trained_on_deeds,
    COUNT(DISTINCT de.id) FILTER (WHERE de.tier = 'royal_jelly') AS rj_deeds,
    COUNT(DISTINCT de.domain_id) AS domains_covered,
    ARRAY_AGG(DISTINCT de.domain_id) AS domain_list,
    ARRAY_AGG(DISTINCT de.judge_a_id) AS judges_used
FROM writers w
LEFT JOIN graph_edges ge ON ge.source_id = w.id AND ge.edge_type = 'trained_on'
LEFT JOIN deeds de ON de.id = ge.target_id
GROUP BY w.id, w.model_name, w.base_model, w.status, w.eval_loss;

CREATE UNIQUE INDEX ON mv_writer_provenance(writer_id);

-- ─── SILICON UTILIZATION VIEW ────────────────────────
CREATE MATERIALIZED VIEW mv_silicon_utilization AS
SELECT
    s.id AS silicon_id,
    s.hardware,
    s.arch,
    s.power_watts,
    s.location,
    COUNT(DISTINCT ge.id) FILTER (WHERE ge.edge_type = 'ran_on') AS jobs_run,
    COUNT(DISTINCT de.id) AS deeds_produced
FROM silicon s
LEFT JOIN graph_edges ge ON ge.target_id = s.id
LEFT JOIN deeds de ON de.origin_node = s.id
GROUP BY s.id, s.hardware, s.arch, s.power_watts, s.location;

CREATE UNIQUE INDEX ON mv_silicon_utilization(silicon_id);

-- ─── REFRESH FUNCTION ────────────────────────────────
CREATE OR REPLACE FUNCTION refresh_all_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_domain_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_judge_performance;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_writer_provenance;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_silicon_utilization;

    -- Update domain counters
    UPDATE domains d SET
        pair_count = (SELECT COUNT(*) FROM pairs WHERE domain_id = d.id),
        deed_count = (SELECT COUNT(*) FROM deeds WHERE domain_id = d.id),
        rj_count = (SELECT COUNT(*) FROM deeds WHERE domain_id = d.id AND tier = 'royal_jelly'),
        rj_yield = COALESCE(
            (SELECT COUNT(*) FILTER (WHERE tier = 'royal_jelly')::real /
             NULLIF(COUNT(*), 0)::real FROM deeds WHERE domain_id = d.id), 0
        ),
        updated_at = NOW();

    -- Update judge counters
    UPDATE judges j SET
        total_scores = (SELECT COUNT(*) FROM tribunal_scores WHERE judge_id = j.id),
        mean_score = (SELECT AVG(score) FROM tribunal_scores WHERE judge_id = j.id);
END;
$$ LANGUAGE plpgsql;

-- ─── PROVENANCE QUERY FUNCTION ───────────────────────
-- Recursive CTE to walk the graph backward from any node
CREATE OR REPLACE FUNCTION trace_provenance(start_id TEXT, max_depth INTEGER DEFAULT 10)
RETURNS TABLE (
    depth INTEGER,
    node_type TEXT,
    node_id TEXT,
    edge_type TEXT,
    from_id TEXT
) AS $$
WITH RECURSIVE trace AS (
    -- Start node
    SELECT 0 AS depth, target_type AS node_type, target_id AS node_id,
           edge_type, source_id AS from_id
    FROM graph_edges WHERE target_id = start_id
    UNION ALL
    -- Walk backward
    SELECT t.depth + 1, ge.target_type, ge.target_id,
           ge.edge_type, ge.source_id
    FROM trace t
    JOIN graph_edges ge ON ge.target_id = t.from_id
    WHERE t.depth < max_depth
)
SELECT * FROM trace ORDER BY depth;
$$ LANGUAGE sql;

-- ─── DEED INSERT TRIGGER ─────────────────────────────
-- Automatically creates graph edges when a deed is inserted
CREATE OR REPLACE FUNCTION on_deed_insert()
RETURNS TRIGGER AS $$
BEGIN
    -- Pair → Deed edge
    INSERT INTO graph_edges (source_type, source_id, target_type, target_id, edge_type)
    VALUES ('pair', NEW.pair_id::text, 'deed', NEW.id, 'deeded_as');

    -- Pair → Judge A edge
    IF NEW.judge_a_id IS NOT NULL THEN
        INSERT INTO graph_edges (source_type, source_id, target_type, target_id, edge_type, properties)
        VALUES ('pair', NEW.pair_id::text, 'judge', NEW.judge_a_id, 'scored_by',
                jsonb_build_object('score', NEW.judge_a_score));
    END IF;

    -- Pair → Judge B edge
    IF NEW.judge_b_id IS NOT NULL THEN
        INSERT INTO graph_edges (source_type, source_id, target_type, target_id, edge_type, properties)
        VALUES ('pair', NEW.pair_id::text, 'judge', NEW.judge_b_id, 'scored_by',
                jsonb_build_object('score', NEW.judge_b_score));
    END IF;

    -- Pair → Domain edge
    INSERT INTO graph_edges (source_type, source_id, target_type, target_id, edge_type)
    VALUES ('pair', NEW.pair_id::text, 'domain', NEW.domain_id, 'belongs_to');

    -- Audit log
    INSERT INTO audit_log (action, entity_type, entity_id, details)
    VALUES ('deed_created', 'deed', NEW.id,
            jsonb_build_object('tier', NEW.tier, 'score', NEW.final_score, 'domain', NEW.domain_id));

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_deed_insert
AFTER INSERT ON deeds
FOR EACH ROW EXECUTE FUNCTION on_deed_insert();

-- ─── ANCHOR INSERT TRIGGER ───────────────────────────
CREATE OR REPLACE FUNCTION on_anchor_insert()
RETURNS TRIGGER AS $$
BEGIN
    -- Batch → Anchor edge
    IF NEW.batch_id IS NOT NULL THEN
        INSERT INTO graph_edges (source_type, source_id, target_type, target_id, edge_type)
        VALUES ('batch', NEW.batch_id, 'anchor', NEW.id, 'anchored_to');
    END IF;

    INSERT INTO audit_log (action, entity_type, entity_id, details)
    VALUES ('anchor_created', 'anchor', NEW.id,
            jsonb_build_object('topic', NEW.hedera_topic, 'merkle_root', NEW.merkle_root));

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_anchor_insert
AFTER INSERT ON anchors
FOR EACH ROW EXECUTE FUNCTION on_anchor_insert();
