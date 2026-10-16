CREATE OR REPLACE VIEW applications_needing_attention AS
SELECT
    a.application_id,
    j.company,
    j.job_title,
    a.source,
    a.applied_at::date AS applied_date,
    CURRENT_DATE - a.applied_at::date AS days_waiting,
    'No qualifying response or outcome event recorded'
        AS attention_reason
FROM applications a
JOIN jobs j
    ON j.job_id = a.job_id
WHERE
    CURRENT_DATE - a.applied_at::date >= 3
    AND NOT EXISTS (
        SELECT 1
        FROM application_events e
        WHERE e.application_id = a.application_id
          AND e.event_type IN (
              'RECRUITER_CONTACTED',
              'ASSESSMENT_RECEIVED',
              'ASSESSMENT_COMPLETED',
              'INTERVIEW_SCHEDULED',
              'INTERVIEW_COMPLETED',
              'OFFER_RECEIVED',
              'REJECTED'
          )
    );