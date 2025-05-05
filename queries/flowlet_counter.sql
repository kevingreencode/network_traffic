-- SQL Query: Count Flowlets Based on 50ms Inter-Arrival Gaps (Outbound)

WITH flow_ordered AS (
    SELECT
        id,
        src_ip,
        dst_ip,
        src_l4_port,
        dst_l4_port,
        protocol,
        timestamp_seconds,
        LAG(timestamp_seconds) OVER (
            PARTITION BY src_ip, dst_ip, src_l4_port, dst_l4_port, protocol
            ORDER BY timestamp_seconds
        ) AS prev_ts
    FROM
        packets
    WHERE
        src_l4_port IS NOT NULL
        AND dst_l4_port IS NOT NULL
        AND capture_direction = 'out'
),
flowlet_marks AS (
    SELECT *,
        CASE
            WHEN prev_ts IS NULL OR timestamp_seconds - prev_ts > 0.05 THEN 1
            ELSE 0
        END AS is_new_flowlet
    FROM flow_ordered
)
SELECT
    COUNT(*) AS estimated_outbound_flowlet_count
FROM flowlet_marks
WHERE is_new_flowlet = 1;
