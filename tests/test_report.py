import pytest

from psycopg.errors import CheckViolation, ForeignKeyViolation

from src.ingestion import (

    find_possible_duplicates,

    normalize_job_url,

)

from src.analysis.generate_report import classify_events, generate_report

from src.database.connection import get_connection

from src.ingestion import add_job, preview_job

# Unit tests: classify application events independently.
def test_no_events_means_no_recorded_response():

    assert classify_events([]) == "NO_RECORDED_RESPONSE"

def test_application_submitted_means_no_recorded_response():

    assert classify_events(["APPLICATION_SUBMITTED"]) == "NO_RECORDED_RESPONSE"

def test_rejection_event_is_classified_correctly():

    assert classify_events(["REJECTED"]) == "REJECTED"

def test_interview_event_is_classified_correctly():

    assert classify_events(["INTERVIEW_SCHEDULED"]) == "INTERVIEW_SCHEDULED"

def test_recruiter_contact_is_other_progress():

    assert classify_events(["RECRUITER_CONTACTED"]) == "OTHER_PROGRESS"

def test_latest_rejection_takes_precedence_over_earlier_interview():

    events = [

        "APPLICATION_SUBMITTED",

        "INTERVIEW_SCHEDULED",

        "REJECTED",

    ]

    assert classify_events(events) == "REJECTED"

# Integration tests: use the current sample database.
def test_report_contains_expected_sections():

    report = generate_report()

    assert "total_applications" in report

    assert "applications_by_source" in report

    assert "application_progress" in report

    assert "source_interview_rates" in report

    assert "applications_needing_attention" in report

    assert "application_funnel" in report

def test_report_total_matches_application_rows():

    report = generate_report()

    assert report["total_applications"] == len(

        report["application_progress"]

    )

def test_insightworks_without_response_is_not_rejected():

    report = generate_report()

    progress_by_company = {

        application[1]: application[4]

        for application in report["application_progress"]

    }

    assert progress_by_company["InsightWorks"] == "NO_RECORDED_RESPONSE"

def test_datacorp_rejection_is_recorded_correctly():

    report = generate_report()

    progress_by_company = {

        application[1]: application[4]

        for application in report["application_progress"]

    }

    assert progress_by_company["DataCorp"] == "REJECTED"

def test_source_interview_rates_are_included_in_report():

    report = generate_report()

    assert len(report["source_interview_rates"]) > 0

    rates_by_source = {

        row[0]: row[3]

        for row in report["source_interview_rates"]

    }

    assert rates_by_source["LinkedIn"] == 100.00

    assert rates_by_source["Naukri"] == 0.00

    assert rates_by_source["Indeed"] == 0.00

def test_attention_report_includes_reason():

    report = generate_report()

    attention_by_company = {

        row[1]: row

        for row in report["applications_needing_attention"]

    }

    assert "InsightWorks" in attention_by_company

    insightworks = attention_by_company["InsightWorks"]

    assert insightworks[5] == (

        "No qualifying response or outcome event recorded"

    )

def test_application_funnel_metrics_are_correct():

    report = generate_report()

    assert report["application_funnel"] == (3, 1, 1, 2, 1)

# Job-event integration tests.
# Each test rolls back its own database changes.
def test_job_found_event_is_stored_correctly():

    with get_connection() as conn:

        try:

            with conn.cursor() as cur:

                cur.execute(

                    """

                    INSERT INTO jobs (company, job_title)

                    VALUES (

                        'Temporary Test Company',

                        'Temporary Test Analyst'

                    )

                    RETURNING job_id;

                    """

                )

                job_id = cur.fetchone()[0]

                cur.execute(

                    """

                    INSERT INTO job_events (

                        user_id,

                        job_id,

                        event_type,

                        source,

                        notes

                    )

                    VALUES (

                        1,

                        %s,

                        'JOB_FOUND',

                        'LinkedIn',

                        'Automated test event'

                    );

                    """,

                    (job_id,),

                )

                cur.execute(

                    """

                    SELECT

                        je.event_type,

                        je.source,

                        j.company

                    FROM job_events je

                    JOIN jobs j ON j.job_id = je.job_id

                    WHERE je.job_id = %s;

                    """,

                    (job_id,),

                )

                row = cur.fetchone()

            assert row == (

                "JOB_FOUND",

                "LinkedIn",

                "Temporary Test Company",

            )

        finally:

            conn.rollback()

def test_job_events_reject_unsupported_event_types():

    with get_connection() as conn:

        try:

            with conn.cursor() as cur:

                cur.execute(

                    """

                    INSERT INTO jobs (company, job_title)

                    VALUES (

                        'Temporary Test Company',

                        'Temporary Test Analyst'

                    )

                    RETURNING job_id;

                    """

                )

                job_id = cur.fetchone()[0]

                with pytest.raises(CheckViolation):

                    with conn.transaction():

                        cur.execute(

                            """

                            INSERT INTO job_events (

                                user_id,

                                job_id,

                                event_type

                            )

                            VALUES (1, %s, 'JOB_REJECTED');

                            """,

                            (job_id,),

                        )

        finally:

            conn.rollback()

def test_job_save_status_view_tracks_save_and_unsave():

    with get_connection() as conn:

        try:

            with conn.cursor() as cur:

                # Create a temporary job.
                cur.execute(

                    """

                    INSERT INTO jobs (company, job_title)

                    VALUES (

                        'Save Status Test Co',

                        'Test Analyst'

                    )

                    RETURNING job_id;

                    """

                )

                job_id = cur.fetchone()[0]

                # Initially, no save action means UNKNOWN.
                cur.execute(

                    """

                    SELECT save_status

                    FROM job_save_status

                    WHERE job_id = %s;

                    """,

                    (job_id,),

                )

                assert cur.fetchone()[0] == "UNKNOWN"

                # Record a save action.
                cur.execute(

                    """

                    INSERT INTO job_events (

                        user_id, job_id, event_type

                    )

                    VALUES (1, %s, 'JOB_SAVED');

                    """,

                    (job_id,),

                )

                cur.execute(

                    """

                    SELECT save_status

                    FROM job_save_status

                    WHERE job_id = %s;

                    """,

                    (job_id,),

                )

                assert cur.fetchone()[0] == "SAVED"

                # Record an unsave action.
                cur.execute(

                    """

                    INSERT INTO job_events (

                        user_id, job_id, event_type

                    )

                    VALUES (1, %s, 'JOB_UNSAVED');

                    """,

                    (job_id,),

                )

                cur.execute(

                    """

                    SELECT save_status

                    FROM job_save_status

                    WHERE job_id = %s;

                    """,

                    (job_id,),

                )

                assert cur.fetchone()[0] == "UNSAVED"

        finally:

            conn.rollback()

# Ingestion integration tests.
def test_add_job_creates_job_and_discovery_event():

    job_id = None

    try:

        job_id = add_job(

            user_id=1,

            company="Ingestion Function Test Co",

            job_title="Test Data Analyst",

            source="Automated Test",

            notes="Temporary test record",

        )

        with get_connection() as conn:

            with conn.cursor() as cur:

                cur.execute(

                    """

                    SELECT

                        j.company,

                        j.job_title,

                        je.event_type,

                        je.source,

                        je.notes

                    FROM jobs j

                    JOIN job_events je

                      ON je.job_id = j.job_id

                    WHERE j.job_id = %s

                      AND je.user_id = 1;

                    """,

                    (job_id,),

                )

                assert cur.fetchone() == (

                    "Ingestion Function Test Co",

                    "Test Data Analyst",

                    "JOB_FOUND",

                    "Automated Test",

                    "Temporary test record",

                )

    finally:

        # add_job commits its own transaction, so clean up explicitly.
        if job_id is not None:

            with get_connection() as conn:

                with conn.cursor() as cur:

                    cur.execute(

                        """

                        DELETE FROM job_events

                        WHERE job_id = %s

                          AND user_id = 1

                          AND event_type = 'JOB_FOUND'

                          AND source = 'Automated Test'

                          AND notes = 'Temporary test record';

                        """,

                        (job_id,),

                    )

                    cur.execute(

                        """

                        DELETE FROM jobs

                        WHERE job_id = %s

                          AND company = 'Ingestion Function Test Co'

                          AND job_title = 'Test Data Analyst';

                        """,

                        (job_id,),

                    )

def test_add_job_rolls_back_when_event_insert_fails():

    # Choose a user ID that does not exist, while still passing Python validation.
    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute("SELECT COALESCE(MAX(user_id), 0) + 1 FROM users;")

            nonexistent_user_id = cur.fetchone()[0]

    with pytest.raises(ForeignKeyViolation):

        add_job(

            user_id=nonexistent_user_id,

            company="Rollback Test Co",

            job_title="Test Analyst",

            source="Automated Test",

        )

    # The job insert must be rolled back when the JOB_FOUND event insert fails.
    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(

                """

                SELECT COUNT(*)

                FROM jobs

                WHERE company = 'Rollback Test Co'

                  AND job_title = 'Test Analyst';

                """

            )

            assert cur.fetchone()[0] == 0

@pytest.mark.parametrize(

    ("overrides", "expected_message"),

    [

        ({"user_id": 0}, "user_id must be a positive integer."),

        ({"user_id": True}, "user_id must be a positive integer."),

        ({"company": ""}, "company must be a non-empty string."),

        ({"company": "   "}, "company must be a non-empty string."),

        ({"job_title": ""}, "job_title must be a non-empty string."),

        ({"salary_min": -1}, "salary_min cannot be negative."),

        ({"salary_max": -1}, "salary_max cannot be negative."),

        (

            {"salary_min": 900000, "salary_max": 600000},

            "salary_min cannot exceed salary_max.",

        ),

        (

            {"salary_min": "600000"},

            "salary_min must be a number or None.",

        ),

    ],

)

def test_add_job_rejects_invalid_input_before_database_access(

    monkeypatch, overrides, expected_message

):

    def fail_if_database_is_accessed():

        pytest.fail("Database should not be accessed for invalid input.")

    monkeypatch.setattr(

        "src.ingestion.get_connection",

        fail_if_database_is_accessed,

    )

    arguments = {

        "user_id": 1,

        "company": "Validation Test Co",

        "job_title": "Data Analyst",

    }

    arguments.update(overrides)

    with pytest.raises(ValueError, match=expected_message):

        add_job(**arguments)

def test_normalizejob_urlremoves_fragment_and_trailing_slash():

    assert normalize_job_url(

        "HTTPS://Example.com/jobs/123/#details"

    ) == "https://example.com/jobs/123"

def test_normalizejob_urlpreserves_query_parameters():

    assert normalize_job_url(

        "https://example.com/jobs/123?ref=linkedin"

    ) == "https://example.com/jobs/123?ref=linkedin"

def test_normalizejob_urlreturns_none_for_missing_url():

    assert normalize_job_url(None) is None

    assert normalize_job_url("   ") is None

def test_find_possible_duplicates_does_not_modify_database():

    # Exact URL should produce a high-confidence match.
    url_matches = find_possible_duplicates(

        company="TechNova",

        job_title="Data Analyst",

        location="Bengaluru",

        job_url="https://example.com/jobs/data-analyst",

    )

    assert any(

        item["match_type"] == "URL_MATCH"

        and item["confidence"] == "HIGH"

        for item in url_matches

    )

    # Same company/title/location but a different URL should
    # produce a review candidate rather than a URL match.
    review_matches = find_possible_duplicates(

        company="TechNova",

        job_title="Data Analyst",

        location="Bengaluru",

        job_url="https://example.com/jobs/data-analyst?source=test",

    )

    assert any(

        item["match_type"] == "COMPANY_TITLE_LOCATION_MATCH"

        and item["confidence"] == "REVIEW"

        for item in review_matches

    )

def test_find_possible_duplicates_rejects_invalid_url_type():

    with pytest.raises(

        ValueError,

        match="job_url must be a string or None.",

    ):

        find_possible_duplicates(

            company="TechNova",

            job_title="Data Analyst",

            job_url=123,

        )

def test_find_possible_duplicates_rejects_invalid_location_type():

    with pytest.raises(

        ValueError,

        match="location must be a string or None.",

    ):

        find_possible_duplicates(

            company="TechNova",

            job_title="Data Analyst",

            location=123,

        )

def test_preview_job_detects_existing_job_without_writing():

    preview = preview_job(

        user_id=1,

        company="TechNova",

        job_title="Data Analyst",

        location="Bengaluru",

        job_url="https://example.com/jobs/data-analyst",

    )

    assert preview["user_id"] == 1

    assert preview["has_possible_duplicates"] is True

    assert preview["requires_review"] is True

    assert any(

        item["match_type"] == "URL_MATCH"

        for item in preview["possible_duplicates"]

    )

def test_preview_job_handles_new_job_without_duplicates(monkeypatch):

    monkeypatch.setattr(

        "src.ingestion.find_possible_duplicates",

        lambda **_kwargs_: [],

    )

    preview = preview_job(

        user_id=1,

        company="BrandNew Test Company",

        job_title="Unique Test Role",

        location="Remote",

        job_url="https://example.com/unique-test-role",

    )

    assert preview["user_id"] == 1

    assert preview["company"] == "BrandNew Test Company"

    assert preview["job_title"] == "Unique Test Role"

    assert preview["has_possible_duplicates"] is False

    assert preview["possible_duplicates"] == []

    assert preview["requires_review"] is False

@pytest.mark.parametrize("invalid_user_id", [0, -1, True, "1", None])

def test_preview_job_rejectsinvalid_user_idbefore_database_access(

    monkeypatch, invalid_user_id

):

    def fail_if_database_is_accessed(**_kwargs_):

        pytest.fail("Duplicate detection should not run for invalid user_id.")

    monkeypatch.setattr(

        "src.ingestion.find_possible_duplicates",

        fail_if_database_is_accessed,

    )

    with pytest.raises(ValueError, match="user_id"):

        preview_job(

            user_id=invalid_user_id,

            company="Validation Test Co",

            job_title="Data Analyst",

        )

def test_preview_job_does_not_modify_database():

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute("SELECT COUNT(*) FROM jobs")

            jobs_before = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM job_events")

            events_before = cur.fetchone()[0]

    preview_job(

        user_id=1,

        company="TechNova",

        job_title="Data Analyst",

        location="Bengaluru",

        job_url="https://example.com/jobs/data-analyst",

    )

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute("SELECT COUNT(*) FROM jobs")

            jobs_after = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM job_events")

            events_after = cur.fetchone()[0]

    assert jobs_after == jobs_before

    assert events_after == events_before

@pytest.mark.parametrize(
    ("company", "job_title"),
    [
        ("  TECHNOVA  ", "Data Analyst"),
        ("TechNova", "  DATA ANALYST  "),
    ],
)
def test_duplicate_matching_ignores_case_and_outer_spaces(
    monkeypatch, company, job_title
):
    existing_job = (
        999999,
        "TechNova",
        "Data Analyst",
        "Bengaluru",
        None,
    )

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, query):
            pass

        def fetchall(self):
            return [existing_job]

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def cursor(self):
            return FakeCursor()

    monkeypatch.setattr(
        "src.ingestion.get_connection",
        lambda: FakeConnection(),
    )

    matches = find_possible_duplicates(
        company=company,
        job_title=job_title,
        location="  BENGALURU  ",
    )

    assert any(
        item["match_type"] == "COMPANY_TITLE_LOCATION_MATCH"
        for item in matches
    )

def test_normalizejob_urlignores_fragment_and_outer_spaces():

    assert normalize_job_url(

        "  https://example.com/jobs/123/#details  "

    ) == "https://example.com/jobs/123"

def test_normalizejob_urlcurrently_preserves_query_parameters():

    assert normalize_job_url(

        "https://example.com/jobs/123?ref=linkedin"

    ) == "https://example.com/jobs/123?ref=linkedin"

@pytest.mark.parametrize(
    ("job_url", "expected"),
    [
        (
            "HTTPS://EXAMPLE.COM/jobs/123",
            "https://example.com/jobs/123",
        ),
        (
            "https://example.com/jobs/123/",
            "https://example.com/jobs/123",
        ),
        (
            "https://example.com/jobs/123/#details",
            "https://example.com/jobs/123",
        ),
        (
            "https://example.com/jobs/123?ref=linkedin",
            "https://example.com/jobs/123?ref=linkedin",
        ),
        (
            "  https://example.com/jobs/123  ",
            "https://example.com/jobs/123",
        ),
        (
            "",
            None,
        ),
        (
            "   ",
            None,
        ),
        (
            None,
            None,
        ),
    ],
)
def test_normalize_job_url_edge_cases(job_url, expected):
    assert normalize_job_url(job_url) == expected

def test_normalize_job_url_removes_default_https_port():
    assert normalize_job_url(
        "https://example.com:443/jobs/123"
    ) == "https://example.com/jobs/123"

def test_normalize_job_url_preserves_non_default_port():
    assert normalize_job_url(
        "https://example.com:8443/jobs/123"
    ) == "https://example.com:8443/jobs/123"
