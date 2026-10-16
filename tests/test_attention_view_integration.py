
"""Integration tests for the applications needing attention view."""

import os

import pytest

from src.database.connection import get_connection


TEST_DATABASE = "job_hunt_intelligence_test"


def test_withdrawn_application_is_not_needing_attention():
    """A withdrawn application should not appear in the attention view."""

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
                    ("Attention View Test Company", "Test Analyst"),
                )
                job_id = cur.fetchone()[0]

                cur.execute(
                    """
                    INSERT INTO resumes (user_id, resume_name, version)
                    VALUES (%s, %s, %s)
                    RETURNING resume_id;
                    """,
                    (user_id, "Attention View Test Resume", 1),
                )
                resume_id = cur.fetchone()[0]

                cur.execute(
                    """
                    INSERT INTO applications (
                        user_id, job_id, resume_id, applied_at,
                        current_status
                    )
                    VALUES (
                        %s, %s, %s, CURRENT_TIMESTAMP - INTERVAL '10 days',
                        %s
                    )
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

                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM applications_needing_attention
                    WHERE application_id = %s;
                    """,
                    (application_id,),
                )
                attention_count = cur.fetchone()[0]

                assert attention_count == 0, (
                    "A withdrawn application should not appear "
                    "in applications_needing_attention."
                )

    finally:
        with get_connection() as conn:
            with conn.cursor() as cur:
                if application_id is not None:
                    cur.execute(
                        """
                        DELETE FROM application_events
                        WHERE application_id = %s;
                        """,
                        (application_id,),
                    )
                    cur.execute(
                        """
                        DELETE FROM applications
                        WHERE application_id = %s;
                        """,
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
