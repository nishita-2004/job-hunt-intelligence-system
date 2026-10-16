
SELECT
    COUNT(*) AS total_applications,

    COUNT(*) FILTER (
        WHERE EXISTS (
            SELECT 1
            FROM application_events e
            WHERE e.application_id = a.application_id
              AND e.event_type = 'INTERVIEW_SCHEDULED'
        )
    ) AS applications_with_interview,

    COUNT(*) FILTER (
        WHERE EXISTS (
            SELECT 1
            FROM application_events e
            WHERE e.application_id = a.application_id
              AND e.event_type = 'REJECTED'
        )
    ) AS applications_with_rejection,

    COUNT(*) FILTER (
        WHERE EXISTS (
            SELECT 1
            FROM application_events e
            WHERE e.application_id = a.application_id
        )
    ) AS applications_with_recorded_events,

    COUNT(*) FILTER (
        WHERE NOT EXISTS (
            SELECT 1
            FROM application_events e
            WHERE e.application_id = a.application_id
        )
    ) AS applications_without_recorded_events

FROM applications a;
