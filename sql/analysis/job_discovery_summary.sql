
SELECT
    COUNT(*) AS total_job_records,

    COUNT(*) FILTER (
        WHERE j.discovered_at IS NOT NULL
    ) AS jobs_with_discovery_timestamp,

    COUNT(*) FILTER (
        WHERE EXISTS (
            SELECT 1
            FROM job_events je
            WHERE je.job_id = j.job_id
              AND je.event_type = 'JOB_FOUND'
        )
    ) AS jobs_with_recorded_discovery,

    COUNT(*) FILTER (
        WHERE j.discovered_at IS NOT NULL
          AND NOT EXISTS (
              SELECT 1
              FROM job_events je
              WHERE je.job_id = j.job_id
                AND je.event_type = 'JOB_FOUND'
          )
    ) AS jobs_missing_discovery_event,

    COUNT(*) FILTER (
        WHERE EXISTS (
            SELECT 1
            FROM job_events je
            WHERE je.job_id = j.job_id
              AND je.event_type IN ('JOB_SAVED', 'JOB_UNSAVED')
        )
    ) AS jobs_with_recorded_save_activity,

    COUNT(*) FILTER (
        WHERE EXISTS (
            SELECT 1
            FROM applications a
            WHERE a.job_id = j.job_id
        )
    ) AS jobs_with_applications

FROM jobs j;
