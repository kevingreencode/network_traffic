-- Average Payload Size by Direction

SELECT
    capture_direction,
    AVG(payload_length) AS avg_payload_length
FROM
    packets
WHERE
    payload_length IS NOT NULL
GROUP BY
    capture_direction;
