WITH latest_save_action AS (
    SELECT DISTINCT ON (je.user_id, je.job_id)
        je.user_id,
        je.job_id,
        je.event_type,
        je.event_at
    FROM job_events je
    WHERE je.event_type IN (
        'JOB_SAVED',
        'JOB_UNSAVED'
    )
    ORDER BY
        je.user_id,
        je.job_id,
        je.event_at DESC,
        je.job_event_id DESC
)
SELECT
    j.job_id,
    j.company,
    j.job_title,
    lsa.user_id,
    CASE
        WHEN lsa.event_type = 'JOB_SAVED' THEN 'SAVED'
        WHEN lsa.event_type = 'JOB_UNSAVED' THEN 'UNSAVED'
        ELSE 'UNKNOWN'
    END AS save_status,
    lsa.event_at AS last_save_action_at
FROM jobs j
LEFT JOIN latest_save_action lsa
    ON lsa.job_id = j.job_id
ORDER BY j.job_id;
