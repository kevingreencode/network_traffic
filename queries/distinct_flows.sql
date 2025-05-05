-- SQL query to identify all distinct flows and count their occurrences
-- A flow is defined by the 5-tuple: src_ip, dst_ip, src_l4_port, src_l4_port, protocol

SELECT
    src_ip,
    dst_ip,
    src_l4_port,
    dst_l4_port,
    protocol,
    COUNT(*)      AS packet_count,
    SUM(total_length) AS total_bytes
FROM
    packets
WHERE
    src_l4_port IS NOT NULL
    AND dst_l4_port IS NOT NULL
    AND total_length IS NOT NULL
    AND src_ip = '10.0.0.1'
GROUP BY
    src_ip,
    dst_ip,
    src_l4_port,
    dst_l4_port,
    protocol
ORDER BY
    total_bytes DESC;
