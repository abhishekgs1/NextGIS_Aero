INSERT INTO complex_et (
    extension_id,
    resource_id,
    feature_id,
    version_id,
    version_op
)
SELECT
    complex.id,
    complex.resource_id,
    complex.feature_id,
    :p_vid AS anon_1,
    :p_vop AS anon_2
FROM complex
WHERE
    complex.resource_id = :p_rid;
