DROP VIEW IF EXISTS analysis.v_zone_link_match_coverage_review_v23;
DROP VIEW IF EXISTS analysis.v_zone_link_match_excluded_review_v23;
DROP VIEW IF EXISTS analysis.v_zone_link_match_candidate_review_v23;

CREATE OR REPLACE VIEW analysis.v_zone_link_match_candidate_review_v23 AS
WITH classified AS (
    SELECT
        c.*,
        CASE
            WHEN c.structure_review_flag
              OR c.potential_grade_separated
              OR c.link_structure_category <> 'NORMAL_ROAD'
                THEN 'MANUAL_REVIEW_STRUCTURE'
            WHEN c.candidate_grade = 'A'
             AND c.match_rule_code IN ('A_STRONG_OVERLAP', 'A_SHORT_INSIDE')
                THEN 'AUTO_APPLY_CANDIDATE'
            WHEN c.candidate_grade = 'A'
             AND c.match_rule_code IN ('A_NEAR_PARALLEL_CORRIDOR', 'A_JUNCTION_COMPONENT')
                THEN 'MANUAL_REVIEW_A_NEAR_OR_JUNCTION'
            WHEN c.match_rule_code IN ('B_WEAK_OVERLAP', 'B_POTENTIAL_GRADE_SEPARATED')
                THEN 'MANUAL_REVIEW_WEAK_OVERLAP'
            WHEN c.candidate_grade IN ('C', 'D')
                THEN 'MANUAL_REVIEW_CONNECTED'
            ELSE 'MANUAL_REVIEW_OTHER'
        END AS v23_review_bucket,
        CASE
            WHEN c.structure_review_flag
              OR c.potential_grade_separated
              OR c.link_structure_category <> 'NORMAL_ROAD'
                THEN 'grade-separated, elevated, underpass, bridge, tunnel, or connector-like link; do not auto-apply from 2D overlap alone'
            WHEN c.candidate_grade = 'A'
             AND c.match_rule_code IN ('A_STRONG_OVERLAP', 'A_SHORT_INSIDE')
                THEN 'normal road with strong direct overlap or short link mostly inside the protection-zone polygon'
            WHEN c.candidate_grade = 'A'
             AND c.match_rule_code IN ('A_NEAR_PARALLEL_CORRIDOR', 'A_JUNCTION_COMPONENT')
                THEN 'A-grade by near-parallel or junction logic, but field review found side-road and junction false positives possible'
            WHEN c.match_rule_code IN ('B_WEAK_OVERLAP', 'B_POTENTIAL_GRADE_SEPARATED')
                THEN 'weak overlap can be valid, but can also be a long-link or grazing artifact'
            WHEN c.candidate_grade IN ('C', 'D')
                THEN 'near or extended connected candidate; useful for review but not safe enough for automatic update'
            ELSE 'candidate requires manual review before use'
        END AS manual_review_reason,
        CASE
            WHEN NOT (
                    c.structure_review_flag
                 OR c.potential_grade_separated
                 OR c.link_structure_category <> 'NORMAL_ROAD'
                )
             AND c.candidate_grade = 'A'
             AND c.match_rule_code IN ('A_STRONG_OVERLAP', 'A_SHORT_INSIDE')
                THEN true
            ELSE false
        END AS auto_apply_eligible
    FROM analysis.v_zone_link_match_candidate_v2 AS c
)
SELECT
    classified.*
FROM classified;

CREATE OR REPLACE VIEW analysis.v_zone_link_match_excluded_review_v23 AS
WITH classified AS (
    SELECT
        e.*,
        CASE
            WHEN e.structure_review_flag
              OR e.potential_grade_separated
              OR e.link_structure_category <> 'NORMAL_ROAD'
                THEN 'MANUAL_REVIEW_STRUCTURE_EXCLUDED'
            WHEN e.exclusion_code IN ('TOUCH_OR_GRAZE', 'TINY_ADJACENCY', 'NEAR_BUT_UNRELATED_TO_SEED', 'EXTENDED_BUT_NOT_NODE_CONNECTED')
                THEN 'EXCLUDED_VALID'
            WHEN e.exclusion_code = 'NO_AB_SEED'
             AND e.distance_m <= 5
             AND (
                    e.intersection_length_m >= 10
                 OR e.proximity_overlap_length_m >= 20
                )
                THEN 'POSSIBLE_FALSE_NEGATIVE_CONTINUOUS_CORRIDOR'
            WHEN e.exclusion_code = 'NO_AB_SEED'
                THEN 'NO_SEED_REVIEW'
            ELSE 'EXCLUDED_REVIEW_OTHER'
        END AS v23_review_bucket,
        CASE
            WHEN e.structure_review_flag
              OR e.potential_grade_separated
              OR e.link_structure_category <> 'NORMAL_ROAD'
                THEN 'excluded pair is around a grade-separated or structure-like link; keep out of auto rules but inspect if it is near the target corridor'
            WHEN e.exclusion_code IN ('TOUCH_OR_GRAZE', 'TINY_ADJACENCY', 'NEAR_BUT_UNRELATED_TO_SEED', 'EXTENDED_BUT_NOT_NODE_CONNECTED')
                THEN 'field review examples show these are often valid exclusions: grazing, outer-road, or unrelated-axis candidates'
            WHEN e.exclusion_code = 'NO_AB_SEED'
             AND e.distance_m <= 5
             AND (
                    e.intersection_length_m >= 10
                 OR e.proximity_overlap_length_m >= 20
                )
                THEN 'candidate may be part of a continuous target corridor but was dropped because no A/B seed existed'
            WHEN e.exclusion_code = 'NO_AB_SEED'
                THEN 'no A/B seed exists; likely normal no-accepted-candidate state unless visually confirmed otherwise'
            ELSE 'excluded pair requires review before changing the rule'
        END AS manual_review_reason,
        false AS auto_apply_eligible
    FROM analysis.v_zone_link_match_excluded_v2 AS e
)
SELECT
    classified.*
FROM classified;

CREATE OR REPLACE VIEW analysis.v_zone_link_match_coverage_review_v23 AS
WITH candidate_rollup AS (
    SELECT
        zone_id,
        COUNT(*)::integer AS v23_candidate_count,
        COUNT(*) FILTER (WHERE auto_apply_eligible)::integer AS auto_apply_candidate_count,
        COUNT(*) FILTER (WHERE v23_review_bucket LIKE 'MANUAL_REVIEW%')::integer AS manual_review_candidate_count,
        COUNT(*) FILTER (WHERE v23_review_bucket = 'MANUAL_REVIEW_STRUCTURE')::integer AS structure_review_candidate_count
    FROM analysis.v_zone_link_match_candidate_review_v23
    GROUP BY zone_id
),
excluded_rollup AS (
    SELECT
        zone_id,
        COUNT(*)::integer AS v23_excluded_count,
        COUNT(*) FILTER (WHERE v23_review_bucket = 'EXCLUDED_VALID')::integer AS valid_excluded_count,
        COUNT(*) FILTER (WHERE v23_review_bucket = 'POSSIBLE_FALSE_NEGATIVE_CONTINUOUS_CORRIDOR')::integer AS possible_false_negative_count,
        COUNT(*) FILTER (WHERE v23_review_bucket = 'MANUAL_REVIEW_STRUCTURE_EXCLUDED')::integer AS structure_review_excluded_count
    FROM analysis.v_zone_link_match_excluded_review_v23
    GROUP BY zone_id
)
SELECT
    cov.*,
    COALESCE(cr.v23_candidate_count, 0) AS v23_candidate_count,
    COALESCE(cr.auto_apply_candidate_count, 0) AS auto_apply_candidate_count,
    COALESCE(cr.manual_review_candidate_count, 0) AS manual_review_candidate_count,
    COALESCE(cr.structure_review_candidate_count, 0) AS structure_review_candidate_count,
    COALESCE(er.v23_excluded_count, 0) AS v23_excluded_count,
    COALESCE(er.valid_excluded_count, 0) AS valid_excluded_count,
    COALESCE(er.possible_false_negative_count, 0) AS possible_false_negative_count,
    COALESCE(er.structure_review_excluded_count, 0) AS structure_review_excluded_count,
    CASE
        WHEN COALESCE(cr.auto_apply_candidate_count, 0) > 0
            THEN 'AUTO_APPLY_READY'
        WHEN COALESCE(er.possible_false_negative_count, 0) > 0
            THEN 'POSSIBLE_FALSE_NEGATIVE_REVIEW'
        WHEN COALESCE(cr.structure_review_candidate_count, 0) + COALESCE(er.structure_review_excluded_count, 0) > 0
            THEN 'STRUCTURE_MANUAL_REVIEW'
        WHEN COALESCE(cr.manual_review_candidate_count, 0) > 0
            THEN 'MANUAL_REVIEW_ONLY'
        WHEN cov.coverage_status = 'NO_CANDIDATE_WITHIN_20M'
            THEN 'VALID_NO_STANDARD_LINK_CANDIDATE'
        WHEN cov.coverage_status = 'NO_ACCEPTED_CANDIDATE'
            THEN 'VALID_NO_ACCEPTED_CANDIDATE'
        ELSE cov.coverage_status
    END AS v23_coverage_bucket
FROM analysis.v_zone_link_match_coverage_v2 AS cov
LEFT JOIN candidate_rollup AS cr
  ON cr.zone_id = cov.zone_id
LEFT JOIN excluded_rollup AS er
  ON er.zone_id = cov.zone_id;

COMMENT ON VIEW analysis.v_zone_link_match_candidate_review_v23 IS
    'Review-bucket interpretation layer for v2 standard-link candidates; separates auto-apply candidates from manual review cases';
COMMENT ON VIEW analysis.v_zone_link_match_excluded_review_v23 IS
    'Review-bucket interpretation layer for excluded v2 standard-link pairs; highlights valid exclusions and possible false negatives';
COMMENT ON VIEW analysis.v_zone_link_match_coverage_review_v23 IS
    'Zone-level v2.3 matching coverage summary for QGIS review and later automated update gating';
