
SELECT
    COALESCE(a.source, 'Unknown') AS source,
    COUNT(*) AS total_applications,

    COUNT(*) FILTER (
        WHERE EXISTS (
            SELECT 1
            FROM application_events e
            WHERE e.application_id = a.application_id
              AND e.event_type = 'INTERVIEW_SCHEDULED'
        )
    ) AS applications_with_interview,
    ROUND(
    100.0 * COUNT(*) FILTER (
        WHERE EXISTS (
            SELECT 1
            FROM application_events e
            WHERE e.application_id = a.application_id
              AND e.event_type = 'INTERVIEW_SCHEDULED'
        )
    ) / NULLIF(COUNT(*), 0),
    2
) AS interview_rate_percent,

    COUNT(*) FILTER (
        WHERE EXISTS (
            SELECT 1
            FROM application_events e
            WHERE e.application_id = a.application_id
              AND e.event_type = 'REJECTED'
        )
    ) AS applications_with_rejection,

    COUNT(*) FILTER (
        WHERE NOT EXISTS (
            SELECT 1
            FROM application_events e
            WHERE e.application_id = a.application_id
              AND e.event_type IN (
                  'INTERVIEW_SCHEDULED',
                  'REJECTED',
                  'OFFER_RECEIVED'
              )
        )
    ) AS applications_without_recorded_outcome

FROM applications a
GROUP BY COALESCE(a.source, 'Unknown')
ORDER BY total_applications DESC, source;