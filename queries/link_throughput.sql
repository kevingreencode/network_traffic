-- SQL Query: Total Throughput (Bytes) Per Link

SELECT
    l.id AS link_id,
    COALESCE(sw1.name, h1.name) AS endpoint1,
    COALESCE(sw2.name, h2.name) AS endpoint2,
    l.link_type,
    SUM(p.total_length) AS total_bytes,
    MIN(p.timestamp_seconds) AS first_ts,
    MAX(p.timestamp_seconds) AS last_ts,
    ROUND(SUM(p.total_length) / NULLIF(MAX(p.timestamp_seconds) - MIN(p.timestamp_seconds), 0), 2) AS bytes_per_second,
    ROUND((SUM(p.total_length) * 8) / NULLIF(MAX(p.timestamp_seconds) - MIN(p.timestamp_seconds), 0) / 1000, 2) AS kilobits_per_second
FROM
    packets p
JOIN
    links l ON p.src_port_id = l.port1_id OR p.dst_port_id = l.port2_id
LEFT JOIN ports pt1 ON l.port1_id = pt1.id
LEFT JOIN switches sw1 ON pt1.switch_id = sw1.id
LEFT JOIN hosts h1 ON l.link_type LIKE 'host-%' AND sw1.id IS NULL AND pt1.id = l.port1_id

LEFT JOIN ports pt2 ON l.port2_id = pt2.id
LEFT JOIN switches sw2 ON pt2.switch_id = sw2.id
LEFT JOIN hosts h2 ON l.link_type LIKE '%-host' AND sw2.id IS NULL AND pt2.id = l.port2_id

WHERE
    p.total_length IS NOT NULL
GROUP BY
    l.id, endpoint1, endpoint2, l.link_type
ORDER BY
    kilobits_per_second DESC;

