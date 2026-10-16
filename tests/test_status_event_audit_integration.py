"""Integration tests for the application status-event audit."""

import os

import pytest

from src.analysis.generate_report import generate_report
from src.database.connection import get_connection


TEST_DATABASE = "job_hunt_intelligence_test"


def test_withdrawn_application_audit_matches_terminal_event():
    """A withdrawn application should agree with its latest event."""

    if os.environ.get("PGDATABASE") != TEST_DATABASE:
        pytest.skip(
            f"Set PGDATABASE={TEST_DATABASE} to run this integration test."
        )

    user_id = None
    job_id = None
    resume_id = None
    application_id = None

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_database();")
                assert cur.fetchone()[0] == TEST_DATABASE

                cur.execute(
                    "INSERT INTO users DEFAULT VALUES RETURNING user_id;"
                )
                user_id = cur.fetchone()[0]

                cur.execute(
                    """
                    INSERT INTO jobs (company, job_title)
                    VALUES (%s, %s)
                    RETURNING job_id;
                    """,
                    ("Status Audit Test Company", "Test Analyst"),
                )
                job_id = cur.fetchone()[0]

                cur.execute(
                    """
                    INSERT INTO resumes (user_id, resume_name, version)
                    VALUES (%s, %s, %s)
                    RETURNING resume_id;
                    """,
                    (user_id, "Status Audit Test Resume", 1),
                )
                resume_id = cur.fetchone()[0]

                cur.execute(
                    """
                    INSERT INTO applications (
                        user_id, job_id, resume_id, current_status
                    )
                    VALUES (%s, %s, %s, %s)
                    RETURNING application_id;
                    """,
                    (user_id, job_id, resume_id, "WITHDRAWN"),
                )
                application_id = cur.fetchone()[0]

                cur.execute(
                    """
                    INSERT INTO application_events (
                        application_id, event_type
                    )
                    VALUES (%s, %s);
                    """,
                    (application_id, "WITHDRAWN"),
                )

        report = generate_report()

        audit_by_id = {
            row[0]: row for row in report["status_event_audit"]
        }
        audit_row = audit_by_id[application_id]

        assert audit_row[3] == "WITHDRAWN"
        assert audit_row[4] == "WITHDRAWN"
        assert audit_row[5] == "NO_RULE_BASED_MISMATCH_DETECTED"

    finally:
        with get_connection() as conn:
            with conn.cursor() as cur:
                if application_id is not None:
                    cur.execute(
                        "DELETE FROM application_events "
                        "WHERE application_id = %s;",
                        (application_id,),
                    )
                    cur.execute(
                        "DELETE FROM applications "
                        "WHERE application_id = %s;",
                        (application_id,),
                    )

                if resume_id is not None:
                    cur.execute(
                        "DELETE FROM resumes WHERE resume_id = %s;",
                        (resume_id,),
                    )

                if job_id is not None:
                    cur.execute(
                        "DELETE FROM jobs WHERE job_id = %s;",
                        (job_id,),
                    )

                if user_id is not None:
                    cur.execute(
                        "DELETE FROM users WHERE user_id = %s;",
                        (user_id,),
                    )

def test_withdrawn_event_with_applied_status_is_flagged():
    """A withdrawn event conflicting with APPLIED status needs review."""

    if os.environ.get("PGDATABASE") != TEST_DATABASE:
        pytest.skip(
            f"Set PGDATABASE={TEST_DATABASE} to run this integration test."
        )

    user_id = None
    job_id = None
    resume_id = None
    application_id = None

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users DEFAULT VALUES RETURNING user_id;"
                )
                user_id = cur.fetchone()[0]

                cur.execute(
                    """
                    INSERT INTO jobs (company, job_title)
                    VALUES (%s, %s)
                    RETURNING job_id;
                    """,
                    ("Status Mismatch Test Company", "Test Analyst"),
                )
                job_id = cur.fetchone()[0]

                cur.execute(
                    """
                    INSERT INTO resumes (user_id, resume_name, version)
                    VALUES (%s, %s, %s)
                    RETURNING resume_id;
                    """,
                    (user_id, "Status Mismatch Test Resume", 1),
                )
                resume_id = cur.fetchone()[0]

                cur.execute(
                    """
                    INSERT INTO applications (
                        user_id, job_id, resume_id, current_status
                    )
                    VALUES (%s, %s, %s, %s)
                    RETURNING application_id;
                    """,
                    (user_id, job_id, resume_id, "APPLIED"),
                )
                application_id = cur.fetchone()[0]

                cur.execute(
                    """
                    INSERT INTO application_events (
                        application_id, event_type
                    )
                    VALUES (%s, %s);
                    """,
                    (application_id, "WITHDRAWN"),
                )

        report = generate_report()

        audit_by_id = {
            row[0]: row for row in report["status_event_audit"]
        }

        assert audit_by_id[application_id][5] == (
            "REVIEW_STATUS_EVENT_MISMATCH"
        )

    finally:
        with get_connection() as conn:
            with conn.cursor() as cur:
                if application_id is not None:
                    cur.execute(
                        "DELETE FROM application_events "
                        "WHERE application_id = %s;",
                        (application_id,),
                    )
                    cur.execute(
                        "DELETE FROM applications "
                        "WHERE application_id = %s;",
                        (application_id,),
                    )

                if resume_id is not None:
                    cur.execute(
                        "DELETE FROM resumes WHERE resume_id = %s;",
                        (resume_id,),
                    )

                if job_id is not None:
                    cur.execute(
                        "DELETE FROM jobs WHERE job_id = %s;",
                        (job_id,),
                    )

                if user_id is not None:
                    cur.execute(
                        "DELETE FROM users WHERE user_id = %s;",
                        (user_id,),
                    )
