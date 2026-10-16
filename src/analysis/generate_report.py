
from src.database.connection import get_connection


def classify_events(event_types):
    """Classify an application using its latest recorded event."""

    if not event_types:
        return "NO_RECORDED_RESPONSE"

    latest_event = event_types[-1]

    if latest_event == "APPLICATION_SUBMITTED":
        return "NO_RECORDED_RESPONSE"

    if latest_event in {
        "INTERVIEW_SCHEDULED",
        "REJECTED",
        "OFFER_RECEIVED",
    }:
        return latest_event

    progress_events = {
        "RECRUITER_CONTACTED",
        "ASSESSMENT_RECEIVED",
        "ASSESSMENT_COMPLETED",
        "INTERVIEW_COMPLETED",
    }

    if latest_event in progress_events:
        return "OTHER_PROGRESS"

    return "OTHER_RECORDED_EVENT"


def generate_report():
    """Fetch data for the Career Intelligence Report."""

    with get_connection() as conn:
        with conn.cursor() as cur:

            # 1. Total applications
            cur.execute("""
                SELECT COUNT(*)
                FROM applications;
            """)
            total_applications = cur.fetchone()[0]

            # 2. Applications by source
            cur.execute("""
                SELECT
                    COALESCE(source, 'Unknown') AS source,
                    COUNT(*) AS applications
                FROM applications
                GROUP BY source
                ORDER BY applications DESC, source;
            """)
            applications_by_source = cur.fetchall()

            # 3. Application progress in chronological event order
            cur.execute("""
                SELECT
                    a.application_id,
                    j.company,
                    j.job_title,
                    a.source,
                    COALESCE(
                        ARRAY_AGG(
                            e.event_type ORDER BY e.event_at, e.event_id
                        ) FILTER (
                            WHERE e.event_type IS NOT NULL
                        ),
                        ARRAY[]::TEXT[]
                    ) AS event_types
                FROM applications a
                JOIN jobs j
                    ON j.job_id = a.job_id
                LEFT JOIN application_events e
                    ON e.application_id = a.application_id
                GROUP BY
                    a.application_id,
                    j.company,
                    j.job_title,
                    a.source
                ORDER BY a.application_id;
            """)
            application_rows = cur.fetchall()

            application_progress = [
                (
                    application_id,
                    company,
                    job_title,
                    source,
                    classify_events(event_types),
                )
                for (
                    application_id,
                    company,
                    job_title,
                    source,
                    event_types,
                ) in application_rows
            ]

            # 4. Interview rates by source.
            # These are historical interview-event rates, not current outcomes.
            cur.execute("""
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
                    ) AS interview_rate_percent

                FROM applications a
                GROUP BY COALESCE(a.source, 'Unknown')
                ORDER BY total_applications DESC, source;
            """)
            source_interview_rates = cur.fetchall()

            # 5. Applications that may need attention
            cur.execute("""
                SELECT
                    application_id,
                    company,
                    job_title,
                    source,
                    days_waiting,
                    attention_reason
                FROM applications_needing_attention
                ORDER BY days_waiting DESC;
            """)
            applications_needing_attention = cur.fetchall()

            # 6. Application funnel summary
            cur.execute("""
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
            """)
            application_funnel = cur.fetchone()

            # 7. Job discovery and activity summary
            cur.execute("""
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
                              AND je.event_type IN (
                                  'JOB_SAVED',
                                  'JOB_UNSAVED'
                              )
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
            """)
            job_discovery_summary = cur.fetchone()

            # 8. Audit stored status against the latest recorded event.
            # This flags potential inconsistencies; it does not update records.
            cur.execute("""
                WITH latest_events AS (
                    SELECT DISTINCT ON (e.application_id)
                        e.application_id,
                        e.event_type AS latest_event_type
                    FROM application_events e
                    ORDER BY
                        e.application_id,
                        e.event_at DESC,
                        e.event_id DESC
                )
                SELECT
                    a.application_id,
                    j.company,
                    j.job_title,
                    a.current_status,
                    le.latest_event_type,
                    CASE
                        WHEN le.latest_event_type IS NULL
                            THEN 'NO_RECORDED_EVENTS'
                        WHEN a.current_status IS NULL
                            THEN 'MISSING_STORED_STATUS'
                        WHEN le.latest_event_type = 'REJECTED'
                             AND a.current_status <> 'REJECTED'
                            THEN 'REVIEW_STATUS_EVENT_MISMATCH'
                        WHEN le.latest_event_type = 'OFFER_RECEIVED'
                             AND a.current_status <> 'OFFER_RECEIVED'
                            THEN 'REVIEW_STATUS_EVENT_MISMATCH'
                        WHEN le.latest_event_type = 'WITHDRAWN'
                            AND a.current_status <> 'WITHDRAWN'
                            THEN 'REVIEW_STATUS_EVENT_MISMATCH'
                        WHEN le.latest_event_type = 'INTERVIEW_SCHEDULED'
                             AND a.current_status = 'APPLIED'
                            THEN 'REVIEW_STATUS_EVENT_MISMATCH'
                        ELSE 'NO_RULE_BASED_MISMATCH_DETECTED'
                    END AS audit_result
                FROM applications a
                JOIN jobs j
                    ON j.job_id = a.job_id
                LEFT JOIN latest_events le
                    ON le.application_id = a.application_id
                ORDER BY a.application_id;
            """)
            status_event_audit = cur.fetchall()

    return {
        "total_applications": total_applications,
        "applications_by_source": applications_by_source,
        "application_progress": application_progress,
        "source_interview_rates": source_interview_rates,
        "applications_needing_attention": applications_needing_attention,
        "application_funnel": application_funnel,
        "job_discovery_summary": job_discovery_summary,
        "status_event_audit": status_event_audit,
    }


def print_report(report):
    """Display the Career Intelligence Report."""

    print("CAREER INTELLIGENCE REPORT")
    print("=" * 40)
    print(f"Total applications: {report['total_applications']}")

    # Applications by source
    print("\nAPPLICATIONS BY SOURCE")
    print("-" * 40)

    for source, count in report["applications_by_source"]:
        print(f"{source}: {count}")

    # Application progress
    print("\nAPPLICATION PROGRESS")
    print("-" * 40)

    for application_id, company, job_title, source, category in (
        report["application_progress"]
    ):
        print(
            f"Application {application_id}: "
            f"{company} - {job_title} | "
            f"{source} | {category}"
        )

    # Historical interview rates
    print("\nHISTORICAL INTERVIEW RATES BY SOURCE")
    print("-" * 40)

    for source, total, interviews, rate in report["source_interview_rates"]:
        print(
            f"{source}: {interviews}/{total} applications had "
            f"an interview scheduled | Historical rate: {rate}%"
        )

    # Applications needing attention
    print("\nAPPLICATIONS THAT MAY NEED ATTENTION")
    print("-" * 40)

    attention_list = report["applications_needing_attention"]

    if not attention_list:
        print("No applications currently meet the attention criteria.")
    else:
        for (
            application_id,
            company,
            job_title,
            source,
            days_waiting,
            attention_reason,
        ) in attention_list:
            print(
                f"Application {application_id}: "
                f"{company} - {job_title} | "
                f"{source} | {days_waiting} days waiting"
            )
            print(f"  Reason: {attention_reason}")

    # Application funnel summary
    print("\nAPPLICATION FUNNEL SUMMARY")
    print("-" * 40)

    (
        total,
        interviews,
        rejections,
        with_events,
        without_events,
    ) = report["application_funnel"]

    print(f"Total applications: {total}")
    print(f"Applications with interview scheduled: {interviews}")
    print(f"Applications with rejection recorded: {rejections}")
    print(f"Applications with recorded events: {with_events}")
    print(f"Applications without recorded events: {without_events}")

    # Job discovery summary
    print("\nJOB DISCOVERY SUMMARY")
    print("-" * 40)

    (
        total_jobs,
        jobs_with_discovery_timestamp,
        jobs_discovered,
        jobs_missing_discovery_event,
        jobs_with_save_activity,
        jobs_with_applications,
    ) = report["job_discovery_summary"]

    print(f"Total job records: {total_jobs}")
    print(
        "Jobs with discovery timestamps: "
        f"{jobs_with_discovery_timestamp}"
    )
    print(f"Jobs with recorded discovery: {jobs_discovered}")
    print(
        "Jobs missing a recorded discovery event: "
        f"{jobs_missing_discovery_event}"
    )
    print(
        "Jobs with recorded save activity: "
        f"{jobs_with_save_activity}"
    )
    print(f"Jobs with applications: {jobs_with_applications}")

    # Status/event-history audit
    print("\nSTATUS / EVENT-HISTORY AUDIT")
    print("-" * 40)

    for (
        application_id,
        company,
        job_title,
        current_status,
        latest_event,
        audit_result,
    ) in report["status_event_audit"]:
        print(
            f"Application {application_id}: {company} - {job_title} | "
            f"Stored status: {current_status or 'MISSING'} | "
            f"Latest recorded event: {latest_event or 'NONE'} | "
            f"Audit: {audit_result}"
        )

    print(
        "\nAudit note: Flags identify records for review, not confirmed errors. "
        "Missing events do not prove that an action never happened."
    )


def main():
    """Generate and display the Career Intelligence Report."""

    report = generate_report()
    print_report(report)


if __name__ == "__main__":
    main()
