-- SQL query to count packets coming out of each port grouped by switch
-- This query connects packet data with port and switch information

SELECT
    sw.name         AS switch_name,
    p.port_number   AS port_number,
    COUNT(pkt.id)   AS packet_count,
    ROUND(
        COUNT(pkt.id) * 100.0 / (
            SELECT COUNT(*) FROM packets WHERE capture_direction = 'out'
        ), 2
    ) AS percent_of_total
FROM
    packets pkt
JOIN
    ports p ON pkt.src_port_id = p.id
JOIN
    switches sw ON p.switch_id = sw.id
WHERE
    pkt.capture_direction = 'out'
GROUP BY
    sw.name, p.port_number
ORDER BY
    percent_of_total DESC;

