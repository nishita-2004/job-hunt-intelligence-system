
"""Integration tests using the isolated PostgreSQL test database."""

import os

import pytest

from src.database.connection import get_connection
from src.application_lifecycle import record_application_event


TEST_DATABASE = "job_hunt_intelligence_test"


def test_submission_event_updates_real_database():
    """Verify event insertion and status synchronization in PostgreSQL."""

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
                    ("Integration Test Company", "Test Data Analyst"),
                )
                job_id = cur.fetchone()[0]

                cur.execute(
                    """
                    INSERT INTO resumes (user_id, resume_name, version)
                    VALUES (%s, %s, %s)
                    RETURNING resume_id;
                    """,
                    (user_id, "Integration Test Resume", 1),
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
                    (user_id, job_id, resume_id, "APPLICATION_STARTED"),
                )
                application_id = cur.fetchone()[0]

        # The setup transaction has committed, so the function's
        # separate connection can see the application.
        event_id = record_application_event(
            application_id,
            "APPLICATION_SUBMITTED",
            "Integration test",
        )

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT current_status
                    FROM applications
                    WHERE application_id = %s;
                    """,
                    (application_id,),
                )
                assert cur.fetchone()[0] == "APPLIED"

                cur.execute(
                    """
                    SELECT event_type, notes
                    FROM application_events
                    WHERE event_id = %s
                      AND application_id = %s;
                    """,
                    (event_id, application_id),
                )
                assert cur.fetchone() == (
                    "APPLICATION_SUBMITTED",
                    "Integration test",
                )

    finally:
        # Remove only the records created by this test.
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
